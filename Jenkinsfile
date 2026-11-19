// DEMO ONLY: Scan the real GitHub branch using the same Gitleaks command as production.
// Intentionally no build, image push, or Kubernetes deployment.
pipeline {
    agent any
    options {
        timestamps()
        disableConcurrentBuilds()
    }
    stages {
        stage('Checkout demo branch') {
            steps {
                checkout scm
                sh 'git rev-parse --abbrev-ref HEAD || true'
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
        stage('Safe end of demo') {
            steps {
                echo 'No secrets detected; demo stops without push or deploy.'
            }
        }
    }
}
