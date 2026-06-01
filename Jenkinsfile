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
    }

    post {
        always {
            echo 'Cleaning up...'
            cleanWs()
        }
    }
stage('Deploy') {
    steps {
        echo 'Deploying application to the Ubuntu host...'
        // 1. Stop and remove the old container if it's already running
        sh 'docker stop my-monitoring-app || true'
        sh 'docker rm my-monitoring-app || true'
        
        // 2. Run the new container directly on the Ubuntu server network
        sh 'docker run -d --name my-monitoring-app -p 8000:3000 monitoring-exfo:latest'
    }
}
}
