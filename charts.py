import matplotlib
matplotlib.use('Agg')  # GUI nahi chahiye - server pe chalega
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from io import BytesIO


class ChartGenerator:
    """AWS cost charts generate karta hai"""

    def generate_cost_chart(self, cost_data, title, period_label):
        """
        Cost trend chart banao.
        cost_data: list of {'date': datetime, 'cost': float}
        Returns: BytesIO (image bytes)
        """
        if not cost_data:
            return None

        dates = [item['date'] for item in cost_data]
        costs = [item['cost'] for item in cost_data]

        # Figure setup
        fig, ax = plt.subplots(figsize=(10, 5))
        fig.patch.set_facecolor('#1a1a2e')
        ax.set_facecolor('#16213e')

        # Line chart
        ax.plot(dates, costs, color='#00d4ff', linewidth=2.5, marker='o',
                markersize=5, markerfacecolor='#00d4ff')

        # Area fill
        ax.fill_between(dates, costs, alpha=0.15, color='#00d4ff')

        # Styling
        ax.set_title(title, color='white', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Date', color='#aaaaaa', fontsize=10)
        ax.set_ylabel('Cost (USD)', color='#aaaaaa', fontsize=10)

        ax.tick_params(colors='#aaaaaa', labelsize=9)
        ax.spines['bottom'].set_color('#333333')
        ax.spines['left'].set_color('#333333')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        ax.grid(True, alpha=0.15, color='#ffffff')

        # Y axis auto-scale with nice padding
        if costs:
            max_cost = max(costs)
            min_cost = min(costs)
            padding = (max_cost - min_cost) * 0.15 if max_cost != min_cost else max_cost * 0.2
            ax.set_ylim(
                max(0, min_cost - padding),
                max_cost + padding
            )
            # Y axis dollar format
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda x, _: f'${x:.2f}')
            )

        # X axis format
        if len(dates) <= 7:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
        elif len(dates) <= 30:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
            ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
            ax.xaxis.set_major_locator(mdates.MonthLocator())

        plt.xticks(rotation=45)

        # Total cost annotation
        total = sum(costs)
        ax.annotate(
            f'Total: ${total:.2f}',
            xy=(0.98, 0.95),
            xycoords='axes fraction',
            ha='right', va='top',
            color='#00d4ff',
            fontsize=11,
            fontweight='bold'
        )

        # Period label
        ax.annotate(
            period_label,
            xy=(0.02, 0.95),
            xycoords='axes fraction',
            ha='left', va='top',
            color='#aaaaaa',
            fontsize=9
        )

        plt.tight_layout()

        # Image bytes mein save karo
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                    facecolor='#1a1a2e')
        buf.seek(0)
        plt.close()

        return buf

    def prepare_cost_data(self, monitor, days):
        """
        AWS Cost Explorer se data fetch karo aur format karo.
        days: 7, 30, 90, 180
        """
        try:
            from datetime import datetime, timedelta

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            response = monitor.cost_explorer.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost']
            )

            cost_data = []
            for day in response['ResultsByTime']:
                date_str = day['TimePeriod']['Start']
                cost = float(day['Total']['UnblendedCost']['Amount'])
                cost_data.append({
                    'date': datetime.strptime(date_str, '%Y-%m-%d'),
                    'cost': round(cost, 4)
                })

            return cost_data

        except Exception as e:
            print(f"❌ Error fetching chart data: {e}")
            return []


# Test
if __name__ == '__main__':
    from datetime import datetime, timedelta

    gen = ChartGenerator()

    # Fake test data - realistic costs
    test_data = []
    import random
    base = 45.0
    for i in range(30):
        variation = random.uniform(-5, 8)
        base = max(10, base + variation)
        test_data.append({
            'date': datetime.now() - timedelta(days=30-i),
            'cost': round(base, 2)
        })

    chart = gen.generate_cost_chart(test_data, 'AWS Cost - Last 30 Days', 'Last 30 Days')

    if chart:
        with open('test_chart.png', 'wb') as f:
            f.write(chart.read())
        print("Chart saved: test_chart.png")
