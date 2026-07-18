# GIM local data language

The same compact, replayable language is available below plots, before statistical tests, and in the global **Transform** dialog. Double-click a column in the token list to insert its safe name.

## Column tokens

Simple column name:

```text
@price
```

Column name with spaces or symbols:

```text
@{Order Date}
```

## Filter and limit rows

```text
where @age >= 18 and @status == "active"
where contains(@city, "syd")
where notnull(@income)
where @name_right not null
where @name_right is null
head 500
tail 100
sample 250
sort @{Order Date} desc
```

## Select and change columns

```text
keep @customer, @sales, @profit
drop @temporary, @{Unused Flag}
rename @rev as Revenue
derive margin = @revenue - @cost
derive margin_pct = round((@revenue - @cost) / @revenue * 100, 2)
cast @{Order Date} as datetime
fill @income = median
dedupe @customer, @{Order Date}
```

## Supported functions

```text
abs(x), sqrt(x), log(x), log10(x), round(x, n)
lower(x), upper(x), contains(x, text, case=False)
isnull(x), notnull(x), year(x), month(x), day(x), clip(x, low, high)
```

Combine steps using new lines or `|`. Lines beginning with `#` are ignored. Arbitrary imports, attribute access, and unrestricted Python calls are blocked so saved workspaces remain deterministic and replayable.
