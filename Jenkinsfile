pipeline {
    agent any

    stages {
        stage('Hello World') {
            steps {
                echo 'Hello, Kuba! Jenkins is successfully reading the repo.'
                sh 'docker --version' // This checks if Jenkins can talk to Docker
            }
        }
    }
}
