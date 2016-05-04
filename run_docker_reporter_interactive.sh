#!/bin/bash

function environment_variable_error() {
    echo "The environment variables AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_ACCOUNT_ID, and AWS_REPORT_BUCKET need to be defined"
    exit 1
}
# Check environment variables
[[ -z ${AWS_ACCESS_KEY} ]] && environment_variable_error
[[ -z ${AWS_SECRET_KEY} ]] && environment_variable_error
[[ -z ${AWS_REPORT_BUCKET} ]] && environment_variable_error
[[ -z ${AWS_ACCOUNT_ID} ]] && environment_variable_error


docker run -it -e AWS_CONSOLIDATED_BILLING -e AWS_ACCOUNT_ID -e AWS_ACCESS_KEY -e AWS_SECRET_KEY -e AWS_REPORT_BUCKET -e AWS_REPORT_YEAR_MONTH oicrsofteng/aws-reporting bash
