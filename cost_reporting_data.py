__author__ = 'cleung'

import boto
from boto import ec2
from boto.s3.connection import S3Connection
import datetime
import zipfile
import os
import csv
from operator import itemgetter
import pdb
import re

# TODO: need to switch to user:PROJECT from user:PURPOSE

# TODO: not using global variables!
untagged_volume_sum = 0
untagged_s3_sum = 0
untagged_egress_sum = 0
year_month = ""
# can be 'Cost' or 'BlendedCost'
costModel = 'Cost';
if os.environ['AWS_CONSOLIDATED_BILLING']:
    costModel = 'BlendedCost'

class SpreadsheetCache(object):
    def __init__(self):
        self.filename = self.get_file_from_bucket()

        self.spreadsheet = []
        with open(self.filename) as f:
            temp_reader = csv.DictReader(f)
            for row in temp_reader:
                if float(row[costModel]) > 0 and row['RecordType'] == "LineItem":
                    if row['Operation'] == "" and row['UsageType'] == "":
                        row['Operation'] = "ProductName" + row['ProductName']
                        row['UsageType'] = "ProductName" + row['ProductName']
                    self.spreadsheet.append(row)
            del temp_reader

        self.fix_case()
        self.sort_data()

        temp_keepers = set()
        for row in self.spreadsheet:
            temp_keepers.add(row['user:PURPOSE'])
        self.keepers = list(temp_keepers)
        del temp_keepers

        self.resources_tag_dict = {}  # key = resource id, value = {'user:PURPOSE': name, 'user:ENV': yes/}
        self.get_resource_tags()  # populate above dictionary
        self.tag_past_items()

        # regions = self.get_regions()
        # self.live_resources = []
        # for region in regions:
        #     self.live_resources.extend(self.get_instances(region))
        #     self.live_resources.extend(self.get_volumes(region))
        #     # detailed billing report from Amazon does not show snapshot or image IDs :(

    def data(self):
        """Returns spreadsheet (list of dicts)"""
        return self.spreadsheet

    def fix_case(self):
        # A method to operate on the spreadsheet and update the column you need uppered
        # Doesn't return anything, just fixes the spreadsheet
        temp_sheet = list(self.spreadsheet)
        for line in temp_sheet:
            try:
                line['user:PURPOSE'] = line['user:PURPOSE'].upper()
            except KeyError:
                sys.exit("user:PURPOSE not found\n Make sure you setup 'Cost Allocation Tags' in your AWS account and select PURPOSE as one of these!")
            try:
                line['user:ENV'] = line['user:ENV'].upper()
            except:
                sys.exit("user:ENV not found\n Make sure you setup 'Cost Allocation Tags' in your AWS account and select ENV as one of these!")
        self.spreadsheet = list(temp_sheet)
        del temp_sheet

    @staticmethod
    def get_file_from_bucket():
        """Grab today's billing report from the S3 bucket, extract into pwd, return filename
        Eventually: Grab a different month's billing report.
        """
        prefix = os.environ['AWS_ACCOUNT_ID'] + "-aws-billing-detailed-line-items-with-resources-and-tags-"
        # Select desired month using date format "YYYY-MM"
        global year_month
        year_month = str(datetime.date.today().isoformat()[0:7])  # get the latest report for current month
        if re.match(r'\d{4}\-\d{2}', os.environ['AWS_REPORT_YEAR_MONTH']):
            year_month = os.environ['AWS_REPORT_YEAR_MONTH']
#        year_month = "2015-10"  # or select your own month
        csv_filename = prefix + year_month + ".csv"
        zip_filename = csv_filename + ".zip"
        # If local data is older than 1 day, download fresh data.
        # mod_time = os.path.getmtime(csv_filename)
        if not os.path.isfile(csv_filename) or datetime.date.today() - datetime.date.fromtimestamp(os.path.getmtime(csv_filename)) > datetime.timedelta(days=0):
            conn = S3Connection(os.environ['AWS_ACCESS_KEY'], os.environ['AWS_SECRET_KEY'])
            mybucket = conn.get_bucket(os.environ['AWS_REPORT_BUCKET'])
            print "Downloading " + zip_filename + "..."
            mykey = mybucket.get_key(zip_filename)
            mykey.get_contents_to_filename(zip_filename)
            print "Extracting to file " + csv_filename + "..."
            zf = zipfile.ZipFile(zip_filename)
            zf.extractall()
        return csv_filename

    def sort_data(self):
        """Sort data by ResourceId, PURPOSE, ENV, Operation, UsageType, Cost"""
        temp_sheet = list(self.spreadsheet)
        self.spreadsheet = list(sorted(temp_sheet, key=itemgetter('ResourceId', 'user:PURPOSE', 'user:ENV',
                                                                  'Operation', 'UsageType', costModel)))
        del temp_sheet

    def get_resource_tags(self):
        """Modifies (populates) dict of resource_id and {PURPOSE-tag, ENV-tag}-pairs
        v2: Some tags changed over time for a given resource. Retain most recent tag for the dictionary.
        """
        for row in self.spreadsheet:
            if row['ResourceId'] not in self.resources_tag_dict:
                self.resources_tag_dict[row['ResourceId']] = {'user:PURPOSE': row['user:PURPOSE'],
                                                              'user:ENV': row['user:ENV'],
                                                              'age': SpreadsheetCache.get_time_comparator(row)}
            if len(row['user:PURPOSE'].strip()) != 0\
                    and SpreadsheetCache.get_time_comparator(row) > self.resources_tag_dict[row['ResourceId']]['age']:
                self.resources_tag_dict[row['ResourceId']]['user:PURPOSE'] = row['user:PURPOSE']
                self.resources_tag_dict[row['ResourceId']]['age'] = self.get_time_comparator(row)
            if len(row['user:ENV'].strip()) != 0:
                self.resources_tag_dict[row['ResourceId']]['user:ENV'] = row['user:ENV']

    def tag_past_items(self):
        """Tag untagged items if they became tagged at any time in the billing record"""
        copy_list = list(self.spreadsheet)
        i = -1
        print "Tagging past items"
        for row in self.spreadsheet:
            i += 1
            if row['ResourceId'] in self.resources_tag_dict:
                copy_list[i]['user:PURPOSE'] = self.resources_tag_dict[row['ResourceId']]['user:PURPOSE']
                copy_list[i]['user:ENV'] = self.resources_tag_dict[row['ResourceId']]['user:ENV']
        self.spreadsheet = list(copy_list)
        del copy_list

    @staticmethod
    def get_regions():
        regions = ec2.regions()
        region_names = []
        for region in regions:
            region_names.append(region.name)
        return region_names

    @staticmethod
    def credentials():
        return {"aws_access_key_id": os.environ['AWS_ACCESS_KEY'],
                "aws_secret_access_key": os.environ['AWS_SECRET_KEY']}

    @staticmethod
    def get_time_comparator(line_item):
        """Return hours since start of month. Use for comparing time of tagging. Easier than datetime module.
        UsageStartDate entries in billing report are in format '2015-06-08 18:00:00'
        """
        hours = 0
        try:
            date_time = line_item['UsageStartDate']
            day = int(date_time[8:10])
            hour = int(date_time[11:13])
            hours = day*24 + hour
        except KeyError:
            pass
        return hours

    def get_instances(self, region):
        """Return names only"""
        creds = self.credentials()
        try:
            conn = ec2.connect_to_region(region, **creds)
            instances = []
            reservations = conn.get_all_reservations()
            for reservation in reservations:
                for instance in reservation.instances:
                    instances.append(instance)
        except boto.exception.EC2ResponseError:
            return []
        return instances

    def get_volumes(self, region):
        """Return names only"""
        creds = self.credentials()
        try:
            conn = ec2.connect_to_region(region, **creds)
            volumes = conn.get_all_volumes()
        except boto.exception.EC2ResponseError:
            return []
        return volumes

    def get_snapshots(self, region):
        creds = self.credentials()
        try:
            conn = ec2.connect_to_region(region, **creds)
            snapshots = conn.get_all_snapshots(owner='self')
        except boto.exception.EC2ResponseError:
            return []
        return snapshots

    def get_images(self, region):
        """Return images for one given region, owned by self"""
        creds = self.credentials()
        try:
            conn = ec2.connect_to_region(region, **creds)
            images = conn.get_all_images(owners=['self'])
        except boto.exception.EC2ResponseError:
            return []
        return images


def print_data():
    """Dump everything to take a look"""
    with open("blob.csv", 'w') as f:
        fields = ['user:PURPOSE', 'ResourceId', 'Operation', 'UsageType', 'Production?', costModel]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in SC.spreadsheet:
            writer.writerow({'user:PURPOSE': row['user:PURPOSE'],
                             'ResourceId': row['ResourceId'],
                             'Operation': row['Operation'],
                             'UsageType': row['UsageType'],
                             'Production?': row['user:ENV'],
                             costModel: row[costModel]})


def subtotal(line_items):
    """ Returns subtotal for line_items.
    Used for summing costs of this particular usage type, under this Operation, ENV-tag, PURPOSE-tag
    """
    total_cost = 0
    for line in line_items:
        total_cost += float(line[costModel])
    # HACK: need to deal with negative costs
    if total_cost < 0:
        total_cost = 0
    return total_cost


def process_resource(line_items, res_id):
    """Process all the line items with this particular resource ID"""
    usage_types = set([x.get('UsageType') for x in line_items])
    cost_for_this_resource = 0

    for usage_type in usage_types:
        usage_cost = subtotal([line_item for line_item in line_items if line_item['UsageType'] == usage_type])
        keeper = line_items[0].get('user:PURPOSE')
        if keeper == "":
            keeper = "untagged"

        # hack hack hack hack, super sneaky
        zones_full = [item['AvailabilityZone'] for item in line_items if item['UsageType'] == usage_type]
        zones = list(set(zones_full))
        zones.reverse()
        zone = zones[0]  # first: low quality pass

        # status = ""
        # if res_id in [x.id.encode() for x in SC.live_resources]:
        #     status = "confirmed live"
        #     if len(zone.strip()) == 0:  #if first pass bad, try here!
        #         pdb.set_trace()
        #         # TypeError: 'Instance' object has no attribute '__getitem__'
        #         if 'zone' in [x for x in SC.live_resources if x['ResourceId'] == res_id][0]:
        #             zone = [x for x in SC.live_resources if x['ResourceId'] == res_id][0]['zone']

        with open("reports/" + keeper + "_report.csv", 'a') as f:
            fields = ['user:PURPOSE', 'ResourceId',  # 'Status, if available',
                      'AvailabilityZone', 'Operation', 'UsageType', 'Production?', costModel]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writerow({'user:PURPOSE': keeper, 'ResourceId': res_id,
                             # 'Status, if available': status,
                             'AvailabilityZone': zone,
                             'Operation': line_items[0]['Operation'], 'UsageType': usage_type,
                             'Production?': line_items[0]['user:ENV'], costModel: usage_cost})
        cost_for_this_resource += usage_cost

    return cost_for_this_resource


def process_prod_type(line_items):
    """Process all the line items for this particular production type"""
    resources = set([x.get('ResourceId') for x in line_items])
    cost_for_this_production_type = 0
    for resource in resources:
        cost_for_this_resource = process_resource([x for x in line_items if x['ResourceId'] == resource], resource)
        keeper = line_items[0].get('user:PURPOSE')
        if keeper == "":
            keeper = "untagged"
        with open("reports/" + keeper + "_report.csv", 'a') as f:
            fields = ['user:PURPOSE', 'ResourceId',  # 'Status, if available',
                      'AvailabilityZone', 'Operation', 'UsageType', 'Production?', costModel, 'subtot', 'subval']
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writerow({'subtot': "Subtotal for resource " + resource, 'subval': cost_for_this_resource})
        cost_for_this_production_type += cost_for_this_resource
    return cost_for_this_production_type


def generate_one_report(keeper):
    """Output all the subtotal info for the specified keeper"""
    line_items = [x for x in SC.spreadsheet if x['user:PURPOSE'] == keeper]

    #prod_types = set([x.get('user:ENV') for x in line_items])  # should be just "" or "yes" but just in case
    # I think this just becomes PROD now
    prod_types = ['PROD'];

    if keeper == "":
        keeper = "untagged"
    report_name = keeper + "_report.csv"

    print "Generating report for: " + keeper + "..."

    with open("reports/" + report_name, 'w') as f:
        fields = ['user:PURPOSE', 'ResourceId',  # 'Status, if available',
                  'AvailabilityZone', 'Operation', 'UsageType', 'Production?', costModel]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writerow({})
#        writer.writerow({'user:PURPOSE': "Report for " + keeper + " from start of month to " + str(datetime.date.today())})
        writer.writerow({'user:PURPOSE': "Report for " + keeper + " for the month " + year_month})
        writer.writeheader()

        cost_for_keeper = {}
        # bunch all by non-production, production, or anything else in the list
    for prod_type in prod_types:
        # list of all line_items with that prod type, and process them
        cost_for_this_production_type = process_prod_type([line_item for line_item in line_items if line_item['user:ENV'] == prod_type])
        with open("reports/" + report_name, 'a') as f:
            fields = ['user:PURPOSE', 'ResourceId',  # 'Status, if available',
                      'AvailabilityZone', 'Operation', 'UsageType', 'Production?', costModel, 'subtot', 'subval']
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writerow({})
            writer.writerow({'subtot': "Subtotal for [non/]production:", 'subval': cost_for_this_production_type})
            writer.writerow({})
        cost_for_keeper[prod_type] = cost_for_this_production_type

    # K this is ugly but figure it out later
    with open("reports/" + report_name, 'a') as f:
        fields = ['user:PURPOSE', 'ResourceId',  # 'Status, if available',
                  'AvailabilityZone', 'Operation', 'UsageType', 'Production?', costModel, 'subtot', 'subval']
        writer = csv.DictWriter(f, fieldnames=fields)
        total_cost_for_keeper = sum(cost_for_keeper.values())
        writer.writerow({'subtot': "TOTAL FOR " + keeper, 'subval': str(total_cost_for_keeper)})

    return cost_for_keeper


def generate_untagged_overview():
    """Give just the right amount of detail to let us know where all the untagged resources are"""
    print "Generating untagged overview report..."
    unkept = [x for x in SC.spreadsheet if len(x['user:PURPOSE'].strip()) == 0]

    with open("reports/untagged_sorted_reports.csv", 'w') as f:

        # costs by resource
        print " ...by resource..."
        resource_ids = set([x.get('ResourceId') for x in unkept])
        fields = ['ProductName', 'ResourceId',  # 'Resource Status (unknown unless available)',
                  'Total cost for resource']
        writer = csv.DictWriter(f, fieldnames=fields)
#        writer.writerow({'ProductName': "Untagged resources from start of month to " + str(datetime.date.today())})
        writer.writerow({'ProductName': "Untagged resources for month " + year_month})

        writer.writerow({})
        writer.writerow({'ProductName': "Untagged resources, grouped by resource id"})
        writer.writeheader()
        list_of_resources = []
        for resource in resource_ids:
            resource_total = sum([float(x[costModel]) for x in unkept if x['ResourceId'] == resource])

            # expect a resource is of one ProductName type, but if not, dump the list
            product = [x['ProductName'] for x in unkept if x['ResourceId'] == resource]
            # This is awful
            product = list(set(product))
            if len(product) == 1:
                product = str(product[0])
            else:
                product = str(product)

            # status = ""
            # if resource in SC.live_resources:
            #     status = "confirmed live"

            list_of_resources.append(dict(p=product, r=resource,
                                          # s=status,
                                          c=resource_total))
        list_of_resources = sorted(list_of_resources, key=itemgetter('p', 'c'), reverse=True)
        for res in list_of_resources:
            writer.writerow({'ProductName': res['p'], 'ResourceId': res['r'],
                             # 'Resource Status (unknown unless available)': res['s'],
                             'Total cost for resource': res['c']})

        # costs by operation
        print " ...by operation..."
        operations = set([x.get('Operation') for x in unkept])
        fields = ['ProductName', 'Operation', 'Total cost for operation']
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writerow({})
        writer.writerow({})
        writer.writerow({'ProductName': "Untagged resources, costs by Operation"})
        writer.writeheader()
        l_o_ops = []
        for op in operations:
            op_total = sum([float(x[costModel]) for x in unkept if x['Operation'] == op])

            # Sorry this is awful
            # expect a resource is of one ProductName type, but if not, dump the list
            product = [x['ProductName'] for x in unkept if x['ResourceId'] == resource]
            # This is awful
            product = list(set(product))
            if len(product) == 1:
                product = str(product[0])
            else:
                product = str(product)

            l_o_ops.append(dict(p=product, o=op, c=op_total))
        l_o_ops = sorted(l_o_ops, key=itemgetter('p', 'c'), reverse=True)
        for oper in l_o_ops:
            writer.writerow({'ProductName': oper['p'], 'Operation': oper['o'], 'Total cost for operation': oper['c']})

        # costs by usage_type
        print " ...by usage type..."
        usage_types = set([x.get('UsageType') for x in unkept])
        fields = ['ProductName', 'UsageType', 'Total cost for UsageType']
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writerow({})
        writer.writerow({})
        writer.writerow({'ProductName': "Untagged resources, costs by UsageType"})
        writer.writeheader()
        l_o_uses = []
        for usage in usage_types:
            usage_total = sum([float(x[costModel]) for x in unkept if x['UsageType'] == usage])

            # Sorry this is awful, again
            # expect a resource is of one ProductName type, but if not, dump the list
            product = [x['ProductName'] for x in unkept if x['ResourceId'] == resource]
            # This is awful
            product = list(set(product))
            if len(product) == 1:
                product = str(product[0])
            else:
                product = str(product)

            l_o_uses.append(dict(p=product, u=usage, c=usage_total))
        l_o_uses = sorted(l_o_uses, key=itemgetter('p', 'c'), reverse=True)
        for use in l_o_uses:
            writer.writerow({'ProductName': use['p'], 'UsageType': use['u'], 'Total cost for UsageType': use['c']})

        # Generate subtotals for untagged: volumes, snapshots, AMIs, S3, and data egress
        writer.writerow({})

        # global variables! TODO: this, better later
        global untagged_volume_sum
        global untagged_s3_sum
        global untagged_egress_sum

        # Volume usage
        untagged_volume_sum = sum([float(x[costModel]) for x in unkept if "Volume" in x.get('UsageType')])
        writer.writerow({'ProductName': "Untagged total for volumes", 'UsageType': untagged_volume_sum})
        # Snapshots... are not an item listed?
        # AMIs... aren't listed either...
        # S3
        untagged_s3_sum = sum([float(x[costModel]) for x in unkept if "Amazon Simple Storage Service" in x.get('ProductName')])
        writer.writerow({'ProductName': "Untagged total for S3", 'UsageType': untagged_s3_sum})
        # Data egress: based on billing report of Nov 1, any outbound data is identified by:
        #   containing "Out" in the UsageType (ItemDescription confirms outbound data is being charged)
        #  XOR
        #   containing "Out" in the Operation (again, ItemDescription confirms outbound data is being charged)
        #  There are no line items with "Out" in both fields
        #  Nearly no lines without "Out" in one of the two fields where ItemDescription refers to outbound data
        #    ^- exception is some PUT / uploads from S3; however, it does include some other S3 transfer operations

        usage_type_egress = sum([float(x[costModel]) for x in unkept if "Out" in x.get('UsageType')])
        operation_egress = sum([float(x[costModel]) for x in unkept if "Out" in x.get('Operation')])
        untagged_egress_sum = usage_type_egress + operation_egress
        writer.writerow({'ProductName': "Untagged total for data egress (some overlap with S3)",
                         'UsageType': untagged_egress_sum})


def generate_reports():
    """Make reports for list of keepers:
    - individual reports with every line item,
    - one report summarizing tagged,
    - one report summarizing all untagged
    """
    costs_for_keepers = []

    # Individual full reports
    for keeper in SC.keepers:
        cost_for_keeper = generate_one_report(keeper)
        if keeper == '':
            keeper = 'untagged'  # may want to set this earlier
        cost_for_keeper['user:PURPOSE'] = keeper
        costs_for_keepers.append(cost_for_keeper)

    # Overview of untagged resources
    generate_untagged_overview()

    # Summarize
    print "Generating summary report..."
    with open('reports/overall_keep+prod_summary.csv', 'w') as f:
        fields = ['user:PURPOSE', 'non-production subtotal', 'production subtotal', 'user total']
        writer = csv.DictWriter(f, fieldnames=fields)
#        writer.writerow({'user:PURPOSE': "Summary of costs from start of month to " + str(datetime.date.today())})
        writer.writerow({'user:PURPOSE': "Summary of costs for month " + year_month})
        writer.writeheader()
        writer.writerow({})
        for i in range(len(SC.keepers)):
            # ok this is not robust at all, TODO: robustify
            if 'yes' not in costs_for_keepers[i]:
                costs_for_keepers[i]['yes'] = 0
            if '' not in costs_for_keepers[i]:
                costs_for_keepers[i][''] = 0
            total = float(costs_for_keepers[i]['']) + float(costs_for_keepers[i]['yes'])
            writer.writerow({'user:PURPOSE': costs_for_keepers[i]['user:PURPOSE'],
                             'non-production subtotal': costs_for_keepers[i][''],
                             'production subtotal': costs_for_keepers[i]['yes'],
                             'user total': total})
            # extra subtotals for breakdown of untagged costs
            if costs_for_keepers[i]['user:PURPOSE'] is 'untagged':
                writer.writerow({'user:PURPOSE': " untagged subtotal for volume usage", 'user total': untagged_volume_sum})
                writer.writerow({'user:PURPOSE': " untagged subtotal for S3", 'user total': untagged_s3_sum})
                writer.writerow({'user:PURPOSE': " untagged subtotal for data egress (some overlap with S3)",
                                 'user total': untagged_egress_sum})


def main():
    # print_data()  # prints blob of data
    # import pdb; pdb.set_trace()
    # generate_one_report('ADAM')
    # generate_one_report('BRIAN')
    # generate_one_report('DENIS')

    generate_reports()

if __name__ == '__main__':
    SC = SpreadsheetCache()
    main()
