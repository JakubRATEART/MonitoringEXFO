pipeline {
    agent any 

    stages {
        stage('Test') {
            steps {
                // The 'script' block tells Jenkins: "Hey, I'm writing dynamic code here!"
                script {
                    docker.image('node:20-alpine').inside {
                        echo 'Running automated tests inside Node container...'
                        sh 'npm install'
                        sh 'npm test'
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
