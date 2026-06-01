import requests
import os
import tempfile
from pdf2image import convert_from_bytes
from typing import Dict, Any
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

try:
    import ollama
except ImportError:
    ollama = None

logger = logging.getLogger(__name__)

# Use OLLAMA_BASE_URL from environment (set by docker-compose)
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
def extract_pdf_with_vision(
    pdf_url: str,
    prompt: str = """You are analyzing a software version table for fusion splicers. The table has 4 columns:
Column 1: Product Description (product group name)
Column 2: Products (model codes, may have multiple variants per row)
Column 3: Version (software version number)
Column 4: Release date

CRITICAL: Scan the ENTIRE table from top to bottom. There are exactly 6 product models to find:

1. 72C+ (appears under "High Definition" group) - extract its version and date
2. 57C+ (appears under "Core Alignment" group). Extract its version and date
3. 502S (appears under "Active Clad" group) - extract its version and date
4. 402S (find which group it's under) - extract its version and date
5. 72M12+ (appears under "Ribbon" group) - extract its version and date
6. 400S (appears under "Handheld" group) - extract its version and date

Processing Instructions:
- Start from the top row and work downward
- For each product description row, look at the Products column for model codes
- Match the model code to one of the 6 targets above
- Use the Version and Release date columns from that same row
- If you see variants like "TYPE-72C+", "Q102-CA+", "T-57C+", map them to the base model (72C+, 57C+, etc.)
- Look carefully at rows near the bottom - they contain 72M12+ and 400S

Output ONLY valid JSON, no markdown or backticks:
[
  {"model": "T-72C+", "version": "1.32", "release_date": "9 Jul, 2025"},
  {"model": "T-57C+", "version": "1.10", "release_date": "18 Dec, 2025"}
]

You MUST include all 6 models. If you cannot read a version clearly, use your best interpretation. Do not skip models.""",
    model: str = "qwen2.5vl:3b",
    page_num: int = 0,
    timeout: int = 500,
    dpi: int = 72
) -> Dict[str, Any]:
    """
    Download a PDF, convert to image, and send to Ollama vision model for processing.

    Args:
        pdf_url: URL of the PDF to download
        prompt: Text prompt for the vision model
        model: Ollama model to use (default: qwen2.5vl:3b)
        page_num: Which page to extract (0-indexed, default: 0 for first page)
        timeout: Request timeout in seconds
        dpi: DPI for PDF to image conversion (lower = less memory, default: 72)

    Returns:
        Dictionary with extracted response and metadata

    Raises:
        requests.RequestException: If download fails
        Exception: If PDF conversion or Ollama call fails
    """
    if ollama is None:
        raise ImportError("ollama package not installed. Run: pip install ollama")

    temp_image_path = None
    try:
        # 1. Download the PDF
        logger.info(f"Downloading PDF from {pdf_url}...")
        response = requests.get(pdf_url, timeout=timeout)
        response.raise_for_status()

        # 2. Convert PDF to Image
        logger.info(f"Converting PDF page {page_num} to image at {dpi} DPI...")
        images = convert_from_bytes(response.content, dpi=dpi)

        if page_num >= len(images):
            raise ValueError(f"PDF has {len(images)} pages, but page {page_num} requested")

        # 3. Save image to temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            temp_image_path = tmp.name
            images[page_num].save(temp_image_path, format="PNG")
            logger.info(f"Saved temporary image to {temp_image_path}")

        # 4. Send to Ollama vision model
        logger.info(f"Sending to Ollama model {model} for processing...")

        # Memory-optimized settings for different models
        model_options = {
            "temperature": 0.1,  # Low temperature for deterministic/consistent results
            "top_p": 0.9,        # Consistent nucleus sampling
            "seed": 42           # Fixed seed for reproducibility
        }

        # Add RAM-efficient settings for memory-hungry models
        if "qwen" in model.lower():
            model_options.update({
                "num_ctx": 256,      # Minimal context window to save VRAM
                "num_batch": 4,      # Minimal batch size for lowest memory footprint
                "num_gpu": 0,        # CPU-only inference (no VRAM overhead)
                "num_thread": 12     # Maximize CPU threading for efficiency
            })

        try:
            # Create client with the correct host
            client = ollama.Client(host=OLLAMA_BASE_URL)

            def run_inference():
                return client.generate(
                    model=model,
                    prompt=prompt,
                    images=[temp_image_path],
                    stream=False,
                    options=model_options
                )

            # Run inference with 120 second timeout
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_inference)
                result = future.result(timeout=120)

        except FuturesTimeoutError:
            logger.error("Ollama inference timed out after 120 seconds")
            raise
        except TypeError:
            # Fallback for older ollama library versions that don't support host parameter
            logger.info(f"Using fallback connection method to {OLLAMA_BASE_URL}")

            def run_inference_fallback():
                return ollama.generate(
                    model=model,
                    prompt=prompt,
                    images=[temp_image_path],
                    stream=False,
                    options=model_options
                )

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_inference_fallback)
                result = future.result(timeout=120)

        logger.info("Processing complete")
        return {
            "status": "success",
            "model": model,
            "response": result.get("response", ""),
            "metadata": {
                "pdf_url": pdf_url,
                "page_num": page_num,
                "dpi": dpi
            }
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error downloading PDF: {e}")
        raise
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        raise
    finally:
        # 5. Clean up temporary image file
        if temp_image_path and os.path.exists(temp_image_path):
            try:
                os.remove(temp_image_path)
                logger.debug(f"Cleaned up temporary image file: {temp_image_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_image_path}: {e}")


if __name__ == "__main__":
    # Example usage
    try:
        result = extract_pdf_with_vision(
            pdf_url="http://example.com/latest_software.pdf",
            prompt="Extract the table into JSON.",
            model="qwen2.5vl:3b"
        )
        print(result)
    except Exception as e:
        print(f"Failed to process PDF: {e}")
