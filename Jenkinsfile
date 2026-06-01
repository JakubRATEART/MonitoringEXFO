pipeline {
    agent any

    stages {
        stage('Test') {
            steps {
                script {
                    docker.image('python:3.11-slim').inside {
                        echo 'Checking Python syntax...'
                        sh 'python3 -m py_compile *.py || true'
                    }
                }
            }
        }
        
        stage('Build Image') {
            steps {
                echo 'Building production Docker image...'
                sh 'docker build -t monitoring-exfo:latest .'
            }
        }

	stage('Deploy') {
            steps {
                script {
                    // Define dynamic names based on the branch
                    def containerName = "app-${BRANCH_NAME}"
                    def hostPort = (BRANCH_NAME == 'main') ? '8000' : '8001'

                    echo "Deploying ${BRANCH_NAME} to port ${hostPort}..."
                    
                    sh "docker stop ${containerName} || true"
                    sh "docker rm ${containerName} || true"
                    sh "docker run -d --name ${containerName} -p ${hostPort}:8484 monitoring-exfo:latest"
                }
            }
        }
    }
    post {
        always {
            echo 'Cleaning up...'
            cleanWs()
        }
    }
}
