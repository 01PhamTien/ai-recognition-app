pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    stages {
        stage('Kiem tra ma nguon') {
            steps {
                echo 'Bat dau kiem tra repository AI Recognition'
                sh 'git --version'
                sh 'pwd'
            }
        }

        stage('Kiem tra cau truc du an') {
            steps {
                script {
                    if (!fileExists('README.md')) {
                        error 'Khong tim thay README.md'
                    }
                    if (!fileExists('.gitignore')) {
                        error 'Khong tim thay .gitignore'
                    }
                }
                echo 'README.md va .gitignore da ton tai'
                sh 'ls -la'
            }
        }

        stage('Hoan tat') {
            steps {
                echo 'Kiem tra ma nguon thanh cong!'
            }
        }
    }

    post {
        success {
            echo 'Pipeline thanh cong!'
        }
        failure {
            echo 'Pipeline that bai. Hay kiem tra Console Output.'
        }
    }
}
