pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    environment {
        IMAGE_TAG = "${GIT_COMMIT}"
        BACKEND_IMAGE = "ai-recognition-api:${GIT_COMMIT}"
        WORKER_IMAGE = "ai-recognition-worker:${GIT_COMMIT}"
        FRONTEND_IMAGE = "ai-recognition-frontend:${GIT_COMMIT}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                echo "Dang kiem tra commit ${GIT_COMMIT}"
            }
        }

        stage('Lint') {
            steps {
                sh '''
                    python3 -m venv .venv-ci
                    . .venv-ci/bin/activate
                    python -m pip install --upgrade pip
                    pip install -r backend/requirements-dev.txt
                    ruff check backend worker scripts
                '''
                dir('frontend') {
                    sh '''
                        npm ci
                        npm run build
                    '''
                }
            }
        }

        stage('Unit Test') {
            steps {
                sh '''
                    . .venv-ci/bin/activate
                    pytest -q backend/tests
                '''
                dir('frontend') {
                    sh 'npm test'
                }
            }
        }

        stage('Build Docker Images') {
            steps {
                sh '''
                    docker build -f backend/Dockerfile -t "$BACKEND_IMAGE" .
                    docker build -f worker/Dockerfile -t "$WORKER_IMAGE" .
                    docker build -f frontend/Dockerfile --build-arg VITE_API_BASE_URL= -t "$FRONTEND_IMAGE" ./frontend
                '''
            }
        }

        stage('Security Scan - Gitleaks') {
            steps {
                sh '''
                    WORKSPACE_IN_VOLUME="/jenkins-home${WORKSPACE#/var/jenkins_home}"
                    docker run --rm \
                      -v jenkins_home:/jenkins-home \
                      -w "$WORKSPACE_IN_VOLUME" \
                      zricethezav/gitleaks:latest \
                      detect --source . --no-git --redact
                '''
            }
        }

        stage('Security Scan - Trivy') {
            steps {
                sh '''
                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      aquasec/trivy:latest image \
                      --exit-code 1 \
                      --severity CRITICAL \
                      --ignore-unfixed \
                      "$BACKEND_IMAGE"

                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      aquasec/trivy:latest image \
                      --exit-code 1 \
                      --severity CRITICAL \
                      --ignore-unfixed \
                      "$WORKER_IMAGE"

                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      aquasec/trivy:latest image \
                      --exit-code 1 \
                      --severity CRITICAL \
                      --ignore-unfixed \
                      "$FRONTEND_IMAGE"
                '''
            }
        }
    }

    post {
        success {
            echo 'CI thanh cong: lint, unit test, build image va security scan deu dat.'
        }
        failure {
            echo 'CI that bai. Mo Console Output de xem stage va loi cu the.'
        }
        always {
            echo "Ket thuc build cho commit ${GIT_COMMIT}"
        }
    }
}
