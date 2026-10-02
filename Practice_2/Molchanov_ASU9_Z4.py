import requests
from collections import Counter

mbox = requests.get('https://www.py4e.com/code3/mbox.txt').text
all_lines = mbox.split('\n')

authors = []

for line in all_lines:
    if line.startswith("From "):
        parts = line.split()
        if len(parts) > 1:
            email = parts[1]
            authors.append(email)

unique_authors = set(authors)

author_counts = Counter(authors)
top_author, max_emails = author_counts.most_common(1)[0]

print(f"Всего найдено уникальных авторов: {len(unique_authors)}")
print("Список всех авторов:")
for author in unique_authors:
    print(f" - {author}")

print(f"\nАвтор, написавший больше всех писем: {top_author}")
print(f"Количество писем: {max_emails}")