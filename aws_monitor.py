import boto3
from datetime import datetime, timedelta
from botocore.exceptions import ClientError, NoCredentialsError


class AWSMonitor:
    """Fetches data from AWS services: EC2, CloudWatch, Cost Explorer, RDS, S3"""

    def __init__(self, access_key, secret_key, region='ap-south-1'):
        """Initialize all AWS service clients"""
        try:
            self.ec2 = boto3.client('ec2', aws_access_key_id=access_key,
                                    aws_secret_access_key=secret_key, region_name=region)

            self.cloudwatch = boto3.client('cloudwatch', aws_access_key_id=access_key,
                                           aws_secret_access_key=secret_key, region_name=region)

            # Cost Explorer only works in us-east-1 (AWS requirement)
            self.cost_explorer = boto3.client('ce', aws_access_key_id=access_key,
                                              aws_secret_access_key=secret_key, region_name='us-east-1')

            self.rds = boto3.client('rds', aws_access_key_id=access_key,
                                    aws_secret_access_key=secret_key, region_name=region)

            self.s3 = boto3.client('s3', aws_access_key_id=access_key,
                                   aws_secret_access_key=secret_key, region_name=region)

            self.region = region
            print(f"AWSMonitor ready! Region: {region}")

        except Exception as e:
            print(f"AWS client error: {e}")
            raise

    def test_connection(self):
        """Test if AWS credentials are valid by calling describe_regions"""
        try:
            self.ec2.describe_regions(RegionNames=[self.region])
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AuthFailure':
                print("AWS credentials are invalid!")
            elif error_code == 'UnauthorizedOperation':
                print("IAM permissions are missing!")
            else:
                print(f"AWS error: {error_code}")
            return False
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

    def get_ec2_instances(self):
        """Get list of all running EC2 instances with name, type, and state"""
        try:
            response = self.ec2.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    # Instance name is stored in Tags
                    name = 'No Name'
                    if 'Tags' in instance:
                        for tag in instance['Tags']:
                            if tag['Key'] == 'Name':
                                name = tag['Value']
                                break
                    instances.append({
                        'id': instance['InstanceId'],
                        'name': name,
                        'type': instance['InstanceType'],
                        'state': instance['State']['Name']
                    })
            return instances
        except ClientError as e:
            print(f"EC2 error: {e.response['Error']['Code']}")
            return []
        except Exception as e:
            print(f"Error fetching instances: {e}")
            return []

    def get_cpu_utilization(self, instance_id, hours=1):
        """Get average CPU utilization for an EC2 instance over the last N hours"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Average']
            )
            if response['Datapoints']:
                datapoints = sorted(response['Datapoints'], key=lambda x: x['Timestamp'], reverse=True)
                return round(datapoints[0]['Average'], 2)
            return 0.0
        except Exception as e:
            print(f"Error fetching CPU: {e}")
            return None

    def get_today_cost(self):
        """Get today's total AWS spending in USD"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            response = self.cost_explorer.get_cost_and_usage(
                TimePeriod={'Start': today, 'End': tomorrow},
                Granularity='DAILY',
                Metrics=['UnblendedCost']
            )
            if response['ResultsByTime']:
                amount = response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']
                return round(float(amount), 2)
            return 0.0
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                print("Cost Explorer access denied! Check IAM permissions.")
            else:
                print(f"Cost Explorer error: {error_code}")
            return None
        except Exception as e:
            print(f"Error fetching today cost: {e}")
            return None

    def get_month_cost(self):
        """Get total AWS spending for the current month"""
        try:
            first_day = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            response = self.cost_explorer.get_cost_and_usage(
                TimePeriod={'Start': first_day, 'End': tomorrow},
                Granularity='MONTHLY',
                Metrics=['UnblendedCost']
            )
            if response['ResultsByTime']:
                amount = response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']
                return round(float(amount), 2)
            return 0.0
        except ClientError as e:
            print(f"Cost Explorer error: {e.response['Error']['Code']}")
            return None
        except Exception as e:
            print(f"Error fetching month cost: {e}")
            return None

    def get_yesterday_cost(self):
        """Get yesterday's total cost (used for anomaly detection)"""
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            today = datetime.now().strftime('%Y-%m-%d')
            response = self.cost_explorer.get_cost_and_usage(
                TimePeriod={'Start': yesterday, 'End': today},
                Granularity='DAILY',
                Metrics=['UnblendedCost']
            )
            if response['ResultsByTime']:
                amount = response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']
                return round(float(amount), 2)
            return 0.0
        except Exception as e:
            print(f"Error fetching yesterday cost: {e}")
            return None

    def get_weekly_costs(self):
        """Get this week's and last week's costs for comparison"""
        try:
            today = datetime.now()
            this_week_start = (today - timedelta(days=7)).strftime('%Y-%m-%d')
            this_week_end = (today + timedelta(days=1)).strftime('%Y-%m-%d')
            last_week_start = (today - timedelta(days=14)).strftime('%Y-%m-%d')
            last_week_end = (today - timedelta(days=7)).strftime('%Y-%m-%d')

            r1 = self.cost_explorer.get_cost_and_usage(
                TimePeriod={'Start': this_week_start, 'End': this_week_end},
                Granularity='DAILY', Metrics=['UnblendedCost']
            )
            r2 = self.cost_explorer.get_cost_and_usage(
                TimePeriod={'Start': last_week_start, 'End': last_week_end},
                Granularity='DAILY', Metrics=['UnblendedCost']
            )

            this_week = sum(float(day['Total']['UnblendedCost']['Amount']) for day in r1['ResultsByTime'])
            last_week = sum(float(day['Total']['UnblendedCost']['Amount']) for day in r2['ResultsByTime'])

            return round(this_week, 2), round(last_week, 2)
        except Exception as e:
            print(f"Error fetching weekly costs: {e}")
            return None, None

    def get_rds_instances(self):
        """Get list of all RDS database instances"""
        try:
            response = self.rds.describe_db_instances()
            instances = []
            for db in response['DBInstances']:
                instances.append({
                    'id': db['DBInstanceIdentifier'],
                    'engine': f"{db['Engine']} {db['EngineVersion']}",
                    'status': db['DBInstanceStatus'],
                    'instance_class': db['DBInstanceClass'],
                    'storage': db['AllocatedStorage'],
                    'multi_az': db['MultiAZ']
                })
            return instances
        except ClientError as e:
            print(f"RDS error: {e.response['Error']['Code']}")
            return []
        except Exception as e:
            print(f"Error fetching RDS instances: {e}")
            return []

    def get_s3_buckets(self):
        """Get list of all S3 buckets with size and object count from CloudWatch"""
        try:
            response = self.s3.list_buckets()
            buckets = []

            for bucket in response['Buckets']:
                bucket_name = bucket['Name']
                size_bytes = 0
                object_count = 0

                try:
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(days=2)

                    # Get bucket size from CloudWatch
                    size_response = self.cloudwatch.get_metric_statistics(
                        Namespace='AWS/S3',
                        MetricName='BucketSizeBytes',
                        Dimensions=[
                            {'Name': 'BucketName', 'Value': bucket_name},
                            {'Name': 'StorageType', 'Value': 'StandardStorage'}
                        ],
                        StartTime=start_time, EndTime=end_time,
                        Period=86400, Statistics=['Average']
                    )
                    if size_response['Datapoints']:
                        size_bytes = size_response['Datapoints'][-1]['Average']

                    # Get object count from CloudWatch
                    count_response = self.cloudwatch.get_metric_statistics(
                        Namespace='AWS/S3',
                        MetricName='NumberOfObjects',
                        Dimensions=[
                            {'Name': 'BucketName', 'Value': bucket_name},
                            {'Name': 'StorageType', 'Value': 'AllStorageTypes'}
                        ],
                        StartTime=start_time, EndTime=end_time,
                        Period=86400, Statistics=['Average']
                    )
                    if count_response['Datapoints']:
                        object_count = int(count_response['Datapoints'][-1]['Average'])
                except Exception:
                    pass

                size_gb = round(size_bytes / (1024 ** 3), 2)
                buckets.append({
                    'name': bucket_name,
                    'size_gb': size_gb,
                    'object_count': object_count,
                    'created': bucket['CreationDate'].strftime('%d-%m-%Y')
                })

            return buckets
        except ClientError as e:
            print(f"S3 error: {e.response['Error']['Code']}")
            return []
        except Exception as e:
            print(f"Error fetching S3 buckets: {e}")
            return []


if __name__ == '__main__':
    print("AWSMonitor ready! Provide credentials to test.")
