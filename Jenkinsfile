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
    options { timestamps(); disableConcurrentBuilds() }
    stages {
        stage('Checkout demo branch') {
            steps { checkout scm }
        }
        stage('Validate frontend HTML') {
            steps {
                dir('frontend') {
                    sh '''
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
    }
    post {
        failure {
            echo 'Expected demo failure: HTML closing tag missing. Sending Telegram FAILURE.'
            script { notifyTelegram('FAILURE', 'DEMO: HTML validation failed; no images pushed or deployed.') }
        }
        success {
            echo 'Unexpected success: HTML validation passed. No deployment performed.'
        }
    }
}
