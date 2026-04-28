import boto3
from datetime import datetime, timedelta
from botocore.exceptions import ClientError, NoCredentialsError


class AWSMonitor:
    """AWS se data fetch karta hai - EC2, CloudWatch, Cost Explorer"""

    def __init__(self, access_key, secret_key, region='ap-south-1'):
        """
        3 AWS clients banao:
        - ec2: instances ki list ke liye
        - cloudwatch: CPU aur metrics ke liye
        - cost_explorer: billing data ke liye
        """
        try:
            self.ec2 = boto3.client(
                'ec2',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )

            self.cloudwatch = boto3.client(
                'cloudwatch',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )

            # Cost Explorer sirf us-east-1 mein kaam karta hai - AWS ka rule hai
            self.cost_explorer = boto3.client(
                'ce',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name='us-east-1'
            )

            self.region = region
            print(f"✅ AWSMonitor ready! Region: {region}")

        except Exception as e:
            print(f"❌ AWS client error: {e}")
            raise

    def test_connection(self):
        """
        AWS credentials sahi hain ya nahi check karo.
        EC2 regions ki list maango - simple aur fast test hai.
        """
        try:
            self.ec2.describe_regions(RegionNames=[self.region])
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AuthFailure':
                print("❌ AWS credentials galat hain!")
            elif error_code == 'UnauthorizedOperation':
                print("❌ IAM permissions missing hain!")
            else:
                print(f"❌ AWS error: {error_code}")
            return False
        except NoCredentialsError:
            print("❌ Credentials provide nahi kiye!")
            return False
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False

    def get_ec2_instances(self):
        """
        Sirf RUNNING EC2 instances ki list do.
        Har instance ka: ID, naam, type, state.
        """
        try:
            response = self.ec2.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )

            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:

                    # Instance ka naam Tags mein hota hai
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
            print(f"❌ EC2 error: {e.response['Error']['Code']}")
            return []
        except Exception as e:
            print(f"❌ Error fetching instances: {e}")
            return []

    def get_cpu_utilization(self, instance_id, hours=1):
        """
        CloudWatch se ek instance ka average CPU usage nikalo.
        Last 1 ghante ka average deta hai.
        """
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)

            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,        # 1 ghante ka ek data point
                Statistics=['Average']
            )

            if response['Datapoints']:
                # Latest datapoint lo
                datapoints = sorted(
                    response['Datapoints'],
                    key=lambda x: x['Timestamp'],
                    reverse=True
                )
                return round(datapoints[0]['Average'], 2)

            return 0.0

        except ClientError as e:
            print(f"❌ CloudWatch error: {e.response['Error']['Code']}")
            return None
        except Exception as e:
            print(f"❌ Error fetching CPU: {e}")
            return None

    def get_today_cost(self):
        """
        Cost Explorer se aaj ka total AWS spending nikalo.
        Amount dollars mein return karta hai.
        """
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
                print("❌ Cost Explorer access nahi hai! IAM mein enable karo.")
            else:
                print(f"❌ Cost Explorer error: {error_code}")
            return None
        except Exception as e:
            print(f"❌ Error fetching today cost: {e}")
            return None

    def get_month_cost(self):
        """
        Is mahine ka total cost nikalo.
        Mahine ke pehle din se aaj tak.
        """
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
            print(f"❌ Cost Explorer error: {e.response['Error']['Code']}")
            return None
        except Exception as e:
            print(f"❌ Error fetching month cost: {e}")
            return None


    def get_weekly_costs(self):
        """
        Is hafte aur pichle hafte ka cost nikalo comparison ke liye.
        Returns: (this_week_cost, last_week_cost)
        """
        try:
            today = datetime.now()

            # Is hafte - last 7 days
            this_week_start = (today - timedelta(days=7)).strftime('%Y-%m-%d')
            this_week_end = (today + timedelta(days=1)).strftime('%Y-%m-%d')

            # Pichla hafte - 8 to 14 days ago
            last_week_start = (today - timedelta(days=14)).strftime('%Y-%m-%d')
            last_week_end = (today - timedelta(days=7)).strftime('%Y-%m-%d')

            # Is hafte ka cost
            r1 = self.cost_explorer.get_cost_and_usage(
                TimePeriod={'Start': this_week_start, 'End': this_week_end},
                Granularity='DAILY',
                Metrics=['UnblendedCost']
            )

            # Pichle hafte ka cost
            r2 = self.cost_explorer.get_cost_and_usage(
                TimePeriod={'Start': last_week_start, 'End': last_week_end},
                Granularity='DAILY',
                Metrics=['UnblendedCost']
            )

            # Saare daily costs add karo
            this_week = sum(
                float(day['Total']['UnblendedCost']['Amount'])
                for day in r1['ResultsByTime']
            )
            last_week = sum(
                float(day['Total']['UnblendedCost']['Amount'])
                for day in r2['ResultsByTime']
            )

            return round(this_week, 2), round(last_week, 2)

        except ClientError as e:
            print(f"❌ Weekly cost error: {e.response['Error']['Code']}")
            return None, None
        except Exception as e:
            print(f"❌ Error fetching weekly costs: {e}")
            return None, None


# Test - AWS credentials chahiye honge
if __name__ == '__main__':
    print("AWS Monitor Test\n")
    print("Note: Real AWS credentials chahiye test ke liye")
    print("Ye file bot.py se use hogi automatically")
    print("\n✅ aws_monitor.py ready!")
