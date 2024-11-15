#!/bin/bash

# Function to display help information
function show_help() {
  echo "Usage: ./deploy-to-s3.sh [OPTIONS]"
  echo
  echo "A script to deploy static content to an S3 bucket."
  echo
  echo "Options:"
  echo "  -b, --bucket   Specify the S3 bucket name."
  echo "  -h, --help     Show this help message and exit."
  echo
  echo "Example:"
  echo "  ./deploy-to-s3.sh -b keith-haring-staging.livingcontent.co"
  echo
}

# Function to display error and exit
function error_exit() {
  echo "Error: $1"
  echo "Run './deploy-to-s3.sh --help' for usage."
  exit 1
}

# Parse input arguments
while [[ "$1" != "" ]]; do
  case $1 in
    -b | --bucket )
      shift
      BUCKET_NAME=$1
      ;;
    -h | --help )
      show_help
      exit 0
      ;;
    * )
      error_exit "Invalid option: $1"
      ;;
  esac
  shift
done

# Check if bucket name was provided
if [ -z "$BUCKET_NAME" ]; then
  error_exit "Bucket name not specified."
fi

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
  error_exit "AWS CLI not found. Please install the AWS CLI."
fi

# Check if the bucket exists
if ! aws s3 ls "s3://$BUCKET_NAME" &> /dev/null; then
  error_exit "S3 bucket '$BUCKET_NAME' does not exist or you do not have access."
fi

# Sync the current directory to the S3 bucket
echo "Deploying to bucket: $BUCKET_NAME"
aws s3 sync . s3://$BUCKET_NAME/ --delete

# Check if the sync command succeeded
if [ $? -ne 0 ]; then
  error_exit "Failed to sync files to the S3 bucket."
else
  echo "Deployment to $BUCKET_NAME complete."
fi