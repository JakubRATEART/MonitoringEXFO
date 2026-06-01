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
}
