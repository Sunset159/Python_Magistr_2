import sys
import re
from datetime import datetime
from collections import Counter, defaultdict

def solve():
    input_lines = sys.stdin.read().splitlines() # После ввода нажать ctrl+z
    
    orders = []
    
    for line in input_lines:
        line = line.strip()
        if not line:
            continue
            
        date_match = re.match(r"^(\d{2})[./](\d{2})[./](\d{4})(?:[;,]|\s+)(.*)$", line)
        if not date_match:
            continue
            
        day, month, year, rest = date_match.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
        except ValueError:
            continue
            
        price_match = re.search(r'(?:[;,]|\s+)(\d+(?:[.,]\d{1,2})?)$', rest)
        if not price_match:
            continue
            
        price_str = price_match.group(1)
        raw_name = rest[:price_match.start()].strip()
        
        if (raw_name.startswith('"') and raw_name.endswith('"')) or \
           (raw_name.startswith("'") and raw_name.endswith("'")):
            raw_name = raw_name[1:-1].strip()
            
        if not raw_name:
            continue
            
        # Преобразуем цену
        price_val = float(price_str.replace(',', '.'))
        has_float = ('.' in price_str or ',' in price_str)
        
        orders.append({
            'dt': dt,
            'date_str': dt.strftime("%d.%m.%Y"),
            'name': raw_name,
            'price': price_val,
            'has_float': has_float,
            'original_price_str': price_str
        })
        
    if not orders:
        return
        
    print("а)")
    pizza_counts = Counter(o['name'] for o in orders)
    for name, count in pizza_counts.most_common():
        print(f"{name} - {count}")
        
    print("б)")
    daily_sums = defaultdict(float)
    daily_has_float = defaultdict(bool)
    daily_dates = {}
    
    for o in orders:
        d_str = o['date_str']
        daily_sums[d_str] += o['price']
        if o['has_float']:
            daily_has_float[d_str] = True
        if d_str not in daily_dates:
            daily_dates[d_str] = o['dt']
            
    sorted_days = sorted(daily_sums.keys(), key=lambda x: daily_dates[x])
    for d_str in sorted_days:
        if daily_has_float[d_str]:
            print(f"{d_str} {daily_sums[d_str]:.2f}")
        else:
            print(f"{d_str} {int(daily_sums[d_str])}")
            
    print("в)")
    max_order = max(orders, key=lambda o: o['price'])
    if max_order['has_float']:
        print(f"{max_order['date_str']} {max_order['name']} {max_order['price']:.2f}")
    else:
        print(f"{max_order['date_str']} {max_order['name']} {int(max_order['price'])}")
        
    print("г)")
    avg_price = sum(o['price'] for o in orders) / len(orders)
    print(f"{avg_price:.2f}")

if __name__ == "__main__":
    solve()