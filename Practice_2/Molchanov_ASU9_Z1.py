def find_median(arr):
    n = len(arr)
    mid = n // 2
    if n % 2 != 0:
        return float(arr[mid])
    else:
        return (arr[mid - 1] + arr[mid]) / 2.0

n = int(input())

data = [int(input()) for _ in range(n)]

data.sort()

mid = n // 2
if n % 2 != 0:
    lower_half = data[:mid]
    upper_half = data[mid + 1 :]
else:
    lower_half = data[:mid]
    upper_half = data[mid:]

q1 = find_median(lower_half)
q3 = find_median(upper_half)

iqr = q3 - q1

lower_bound = q1 - 1.5 * iqr
upper_bound = q3 + 1.5 * iqr

outliers_count = 0
for x in data:
    if x < lower_bound or x > upper_bound:
        outliers_count += 1

print(outliers_count)