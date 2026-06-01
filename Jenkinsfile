pipeline {
    agent any

    environment {
        // Automatically extracts the branch name safely and strips out 'origin/' if present
        CLEAN_BRANCH = "${env.GIT_BRANCH ? env.GIT_BRANCH.replace('origin/', '') : 'main'}"
    }

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
                    // Use the clean environment variable we defined above
                    def containerName = "app-${env.CLEAN_BRANCH}"
                    def hostPort = (env.CLEAN_BRANCH == 'main') ? '8000' : '8001'

                    echo "Deploying branch [${env.CLEAN_BRANCH}] to host port ${hostPort}..."

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
