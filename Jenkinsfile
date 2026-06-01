pipeline {
    // 1. Tell Jenkins to use any available host executor globally
    agent any 

    stages {
        // Notice: No manual 'Checkout' stage needed! Jenkins does it automatically.

        stage('Test') {
            steps {
                // 2. Instead of changing the whole agent, we run Docker cleanly inside a block
                docker.image('node:20-alpine').inside {
                    echo 'Running automated tests inside Node container...'
                    // Jenkins automatically passes the primary source folder into this block
                    sh 'npm install'
                    sh 'npm test'
                }
            }
        }

        stage('Build Image') {
            steps {
                echo 'Building production Docker image...'
                // If you don't have a Dockerfile yet, change this to a simple echo test
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
