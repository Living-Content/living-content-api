#!/bin/bash

# Function to display help information
function show_help() {
  echo "Usage: ./invalidate-cloudfront.sh [OPTIONS]"
  echo
  echo "A script to invalidate CloudFront distribution."
  echo
  echo "Options:"
  echo "  -d, --distribution-id   Specify the CloudFront distribution ID."
  echo "  -h, --help              Show this help message and exit."
  echo
  echo "Example:"
  echo "  ./invalidate-cloudfront.sh -d E123456789EXAMPLE"
  echo
}

# Function to display error and exit
function error_exit() {
  echo "Error: $1"
  echo "Run './invalidate-cloudfront.sh --help' for usage."
  exit 1
}

# Parse input arguments
while [[ "$1" != "" ]]; do
  case $1 in
    -d | --distribution-id )
      shift
      DISTRIBUTION_ID=$1
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

# Check if distribution ID was provided
if [ -z "$DISTRIBUTION_ID" ]; then
  error_exit "CloudFront distribution ID not specified."
fi

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
  error_exit "AWS CLI not found. Please install the AWS CLI."
fi

# Create CloudFront invalidation
echo "Invalidating CloudFront distribution: $DISTRIBUTION_ID"
aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION_ID" --paths "/*"

# Check if the invalidation command succeeded
if [ $? -ne 0 ]; then
  error_exit "Failed to invalidate CloudFront distribution."
else
  echo "Invalidation for distribution $DISTRIBUTION_ID complete."
fi