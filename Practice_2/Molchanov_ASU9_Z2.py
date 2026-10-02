names = input().split() # Ввод имен
n_people = len(names)

n_purchases = int(input()) # Ввод количества покупок

spent = {name: 0 for name in names}

while True:
    line = input().strip() # Ввод имен и покупок
    if not line:
        break

    person, amount_str = line.split()
    amount = int(amount_str)
    
    if person not in spent:
        spent[person] = 0
    spent[person] += amount * 100 # Траты в копейках

total_spent = sum(spent.values())

base_share = total_spent // n_people
rem = total_spent % n_people # Остаток денег, который не распределился

balances = []
for i, name in enumerate(names):
    target = base_share + (1 if i < rem else 0) # Первые в списке должны на копейку больше, если есть остаток
    net = spent[name] - target
    balances.append([name, net])

debtors = []
creditors = []

for name, net in balances:
    if net < 0:
        debtors.append([name, -net])
    elif net > 0:
        creditors.append([name, net])

transactions = []
i = 0
j = 0

while i < len(debtors) and j < len(creditors):
    debtor_name, debt_amt = debtors[i]
    creditor_name, cred_amt = creditors[j]

    transfer_amt = min(debt_amt, cred_amt)
    transactions.append((debtor_name, creditor_name, transfer_amt / 100.0))

    debtors[i][1] -= transfer_amt
    creditors[j][1] -= transfer_amt

    if debtors[i][1] == 0:
        i += 1
    if creditors[j][1] == 0:
        j += 1

print(len(transactions))
for debtor, creditor, amount in transactions:
    print(f"{debtor} {creditor} {amount:.2f}")