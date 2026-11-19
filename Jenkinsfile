// Telegram credentials are stored in Jenkins, never in this repository.
// Notification errors must not change the CI/CD build result.
def notifyTelegram(String status, String detail) {
    try {
        withCredentials([
            string(credentialsId: 'telegram-bot-token', variable: 'TELEGRAM_BOT_TOKEN'),
            string(credentialsId: 'telegram-chat-id', variable: 'TELEGRAM_CHAT_ID')
        ]) {
            withEnv([
                "TELEGRAM_STATUS=${status}",
                "TELEGRAM_DETAIL=${detail}"
            ]) {
                sh '''#!/bin/sh
set +x
MESSAGE=$(printf 'AI Recognition CI/CD: %s\n%s\nJob: %s\nBuild: #%s\nImage: %s\nJenkins: %s' \
  "$TELEGRAM_STATUS" "$TELEGRAM_DETAIL" "$JOB_NAME" "$BUILD_NUMBER" "${IMAGE_TAG:-N/A}" "${BUILD_URL:-N/A}")
curl --fail --silent --show-error --max-time 15 --retry 2 \
  --request POST \
  --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" \
  --data-urlencode "text=$MESSAGE" \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" > /dev/null
'''
            }
        }
    } catch (Exception error) {
        echo "Khong gui duoc Telegram notification; giu nguyen ket qua CI/CD. (${error.getClass().getSimpleName()})"
    }
}

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.IMAGE_TAG = sh(
                        script: 'git rev-parse --short=12 HEAD',
                        returnStdout: true
                    ).trim()
                }
                echo "Dang kiem tra commit voi image tag ${env.IMAGE_TAG}"
            }
        }

        stage('Lint - Python') {
            steps {
                sh '''
                    python3 -m venv .venv-ci
                    . .venv-ci/bin/activate
                    python -m pip install --upgrade pip
                    pip install -r backend/requirements-dev.txt
                    ruff check backend worker scripts
                '''
            }
        }

        stage('Unit Test') {
            steps {
                sh '''
                    . .venv-ci/bin/activate
                    PYTHONPATH="$WORKSPACE" python -m pytest -q backend/tests
                '''
                dir('frontend') {
                    sh '''
                        npm ci
                        npm test
                        node - <<'NODE'
const fs = require('fs');
const html = fs.readFileSync('index.html', 'utf8');
if (!html.trimEnd().toLowerCase().endsWith('</html>')) {
  console.error('HTML validation failed: missing closing </html> tag');
  process.exit(1);
}
console.log('HTML validation passed');
NODE
                    '''
                }
            }
        }

        stage('Build Docker Images') {
            steps {
                sh '''
                    docker build -f backend/Dockerfile -t "ai-recognition-api:$IMAGE_TAG" .
                    docker build -f worker/Dockerfile -t "ai-recognition-worker:$IMAGE_TAG" .
                    docker build -f frontend/Dockerfile --build-arg VITE_API_BASE_URL= -t "ai-recognition-frontend:$IMAGE_TAG" ./frontend
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
                      "ai-recognition-api:$IMAGE_TAG"

                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      aquasec/trivy:latest image \
                      --exit-code 1 \
                      --severity CRITICAL \
                      --ignore-unfixed \
                      "ai-recognition-worker:$IMAGE_TAG"

                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      aquasec/trivy:latest image \
                      --exit-code 1 \
                      --severity CRITICAL \
                      --ignore-unfixed \
                      "ai-recognition-frontend:$IMAGE_TAG"
                '''
            }
        }

        stage('Push Images - GHCR') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'ghcr-credentials',
                    usernameVariable: 'GHCR_USERNAME',
                    passwordVariable: 'GHCR_TOKEN'
                )]) {
                    sh '''
                        set +x
                        echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin

                        docker tag "ai-recognition-api:$IMAGE_TAG" "ghcr.io/01phamtien/ai-recognition-api:$IMAGE_TAG"
                        docker tag "ai-recognition-worker:$IMAGE_TAG" "ghcr.io/01phamtien/ai-recognition-worker:$IMAGE_TAG"
                        docker tag "ai-recognition-frontend:$IMAGE_TAG" "ghcr.io/01phamtien/ai-recognition-frontend:$IMAGE_TAG"

                        docker push "ghcr.io/01phamtien/ai-recognition-api:$IMAGE_TAG"
                        docker push "ghcr.io/01phamtien/ai-recognition-worker:$IMAGE_TAG"
                        docker push "ghcr.io/01phamtien/ai-recognition-frontend:$IMAGE_TAG"

                        docker logout ghcr.io
                    '''
                }
            }
        }

        stage('Deploy Frontend - Staging') {
            steps {
                echo "CI push thanh cong. Goi CD voi image tag ${env.IMAGE_TAG}"
                build job: 'ai-recognition-deploy-staging',
                    parameters: [
                        string(name: 'IMAGE_TAG', value: env.IMAGE_TAG)
                    ],
                    wait: true,
                    propagate: true
            }
        }
    }

    post {
        success {
            echo 'CI thanh cong: lint, unit test, build image va security scan deu dat.'
            script {
                notifyTelegram('SUCCESS', 'Deploy Frontend Staging thanh cong.')
            }
        }
        failure {
            echo 'CI that bai. Mo Console Output de xem stage va loi cu the.'
            script {
                notifyTelegram('FAILURE', 'Pipeline that bai (co the do CI hoac deploy). Xem Jenkins de biet chi tiet.')
            }
        }
        always {
            echo "Ket thuc build cho image tag ${IMAGE_TAG}"
        }
    }
}
