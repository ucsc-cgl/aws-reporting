# aws-reporting

**Build**

    docker build -t oicrsofteng/aws-reporting .

**How to use**
* Have docker installed
* Have your aws keys as environment variables: AWS_ACCESS_KEY, AWS_SECRET_KEY. The next script will use them in docker
* AWS_REPORT_YEAR_MONTH optional, fomatted like YYYY-MM
* AWS_CONSOLIDATED_BILLING = TRUE if using consolidated billing
* identify the bucket you want the report in, set environment variable AWS_REPORT_BUCKET
* Run <pre>$ bash run_docker_reporter.sh</pre>
* Goto the S3 Bucket to see the reports: https://console.aws.amazon.com/s3/home?region=us-east-1&bucket=oicr.detailed.billing&prefix=reports/

**Costs**
cost_reporting_data.py gets costs so far this month based on the most detailed billing report we have. Coming soon: functionality for selecting previous months.

**Usage**
usage_data.py shows which resources are currently live with associated KEEP- and PROD-tags

**Upload to bucket**
reports_to_bucket.py uploads whatever files were successfully generated into the S3 bucket

**Run Interactively**

    bash run_docker_reporter_interactive.sh
    # within the docker
    python usage_data.py
    python cost_reporting_data.py
    # look in reports directory

**TODO**

Need to switch to:

* ENV=[PROD|DEV], from the PROD tag currently (requires a rethink in the way this works since PROD doesn't look at value)
* PURPOSE=[PROJECT_NAME|IDENTIFIER], from the KEEP tag currently
* docker run -it -v `pwd`/reports:/root/aws-reporting/reports/ -e AWS_CONSOLIDATED_BILLING -e AWS_ACCOUNT_ID -e AWS_ACCESS_KEY -e AWS_SECRET_KEY -e AWS_REPORT_BUCKET -e AWS_REPORT_YEAR_MONTH oicrsofteng/aws-reporting bash
