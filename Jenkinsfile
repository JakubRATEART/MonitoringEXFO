pipeline {
    agent any 

    environment {
        // Define variables to avoid repeating yourself
        REGISTRY_USER = 'jakubrateart'
        IMAGE_NAME    = 'monitoring-exfo'
        IMAGE_TAG     = "${BUILD_NUMBER}" // Uses the sequential Jenkins build number
    }

    stages {
        stage('Checkout') {
            steps {
                // Pulls the latest code from the Git repo configured in your job
                checkout scm
            }
        }

        stage('Test') {
            agent {
                // Spins up a temporary Node/Python/Go container just to run tests
                docker { image 'node:20-alpine' } 
            }
            steps {
                echo 'Running automated tests...'
                // Inside the temporary container, we install dependencies and test
                sh 'npm install'
                sh 'npm test'
            }
        }

        stage('Build Image') {
            steps {
                echo "Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
                // Builds your actual production application image
                sh "docker build -t ${REGISTRY_USER}/${IMAGE_NAME}:${IMAGE_TAG} ."
                sh "docker tag ${REGISTRY_USER}/${IMAGE_NAME}:${IMAGE_TAG} ${REGISTRY_USER}/${IMAGE_NAME}:latest"
            }
        }

        stage('Deploy') {
            steps {
                echo 'Deploying to Ubuntu Server...'
                // 1. Stop and remove the old container if it exists (ignoring errors if it doesn't)
                sh 'docker stop monitoring-app || true'
                sh 'docker rm monitoring-app || true'
                
                // 2. Run the fresh container
                sh "docker run -d --name monitoring-app -p 80:8080 ${REGISTRY_USER}/${IMAGE_NAME}:latest"
            }
        }
    }

    post {
        always {
            echo 'Cleaning up workspace...'
            cleanWs() // Deletes temporary source files from the Jenkins directory to save disk space
        }
        success {
            echo 'Pipeline completed successfully! App is live.'
        }
        failure {
            echo 'Pipeline FAILED. Check the logs above to see which stage broke.'
        }
    }
}
