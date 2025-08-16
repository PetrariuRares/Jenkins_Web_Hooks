# Build the base image
docker build -t trialqlk1tc.jfrog.io/dockertest-docker/python-base:3.11 -f base.Dockerfile .

# Login to Artifactory (your Jenkins script already does this)
docker login trialqlk1tc.jfrog.io

# Push the base image
docker push trialqlk1tc.jfrog.io/dockertest-docker/python-base:3.11