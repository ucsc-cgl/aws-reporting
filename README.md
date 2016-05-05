# aws-reporting

## Build

    docker build -t oicrsofteng/aws-reporting .

## Prepare Your AWS Account

### Setup Detailed Billing

You need to setup detailed billing in your account.

Sign in to the AWS Management Console and open the Billing and Cost Management console athttps://console.aws.amazon.com/billing/home#/.

* On the navigation pane, choose Preferences.
* Select the Receive Billing Reports check box.
* Designate the Amazon S3 bucket where you want AWS to publish your detailed billing reports.
* After your S3 bucket has been verified, under Report, select the check boxes for the reports that you want to receive.
* Choose Save preferences.

Note: It can take up to 24 hours for AWS to start delivering reports to your S3 bucket. After delivery starts, AWS updates the detailed report files multiple times per day.

### Set Cost Allocation Tags

Not all tags will appear by default in the detailed billing report.  You need to setup the ENV and PURPOSE tags in the "Cost Allocation Tags" section of the billing dashboard.

If you don't see the tags listed, make sure you tag at least one instance with these tags first.

## Reporter Installation

* Have docker installed
* Have your AWS keys as environment variables: AWS_ACCESS_KEY, AWS_SECRET_KEY
* Set env var AWS_REPORT_YEAR_MONTH formatted like YYYY-MM, optional, the current month/year used if not set
* AWS_CONSOLIDATED_BILLING = TRUE if using consolidated billing is used on this account (this means the AWS report will use 'BlendedCost' instead of 'Cost')
* Identify the bucket you want the report in, set environment variable AWS_REPORT_BUCKET to that bucket name
* Set the env var AWS_ACCOUNT_ID to your account ID

## Running

This runs all the three commands described below:

    bash run_docker_reporter.sh

## Run Interactively

This is helpful for debugging.  Can run it with this wrapper:

    bash run_docker_reporter_interactive.sh
    # within the docker
    python usage_data.py
    python cost_reporting_data.py
    # look in reports directory

Or do something like this if you want to store the reports on your local computer:

    docker run -it -v `pwd`/../reports:/root/aws-reporting/reports/ -e AWS_CONSOLIDATED_BILLING -e AWS_ACCOUNT_ID -e AWS_ACCESS_KEY -e AWS_SECRET_KEY -e AWS_REPORT_BUCKET -e AWS_REPORT_YEAR_MONTH oicrsofteng/aws-reporting bash

## Components

### Costs
cost_reporting_data.py gets costs so far this month based on the most detailed billing report we have.

### Usage
usage_data.py shows which resources are currently live with associated KEEP- and PROD-tags

### Upload to bucket
reports_to_bucket.py uploads whatever files were successfully generated into the S3 bucket

## TODO

Need to:

* ENV=[PROD|DEV] and possibly additional environments. Requires a rethink in the way this works since ENV is just checked for PROD or !PROD
* PURPOSE=[PROJECT_NAME|IDENTIFIER], this is working but we need to standardize the project names
* Need to support negative values in the detailed billing report. Break these down as a separate credits section of the report
    * in the mean time, need to ensure negative values in the input report from AWS are *ignored*
