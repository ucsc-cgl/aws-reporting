FROM ubuntu:latest

RUN apt-get update && apt-get install -y \
  git \
  python-pip

RUN mkdir /root/aws-reporting
COPY README.md cost_reporting_data.py report_runner.sh reports_to_bucket.py run_docker_reporter.sh usage_data.py /root/aws-reporting/
RUN pip install boto
RUN mkdir /root/aws-reporting/reports
WORKDIR /root/aws-reporting/
