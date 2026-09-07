# Database Schema — Olist E-Commerce (REAL Kaggle data)

Database file: `olist_real.db` (SQLite)
Source: Kaggle "Brazilian E-Commerce Public Dataset by Olist" (olistbr)
Geolocation table excluded (1M rows, out of scope for this project).

## ⚠️ Read this before writing any query

### 1. Two different customer identifiers — do not mix these up
| Column | Meaning | Distinct count (verified) |
|---|---|---|
| `customer_id` | One row created **per order** | 99,441 |
| `customer_unique_id` | Identifies the **actual person** | 96,096 |

3,345 orders come from repeat buyers. Rule of thumb:
- Counting/grouping **orders** → `customer_id` or `order_id`, either fine.
- Counting/grouping **people** ("how many customers", "repeat customers",
  "average orders per customer") → MUST use `customer_unique_id`, or every
  repeat buyer gets counted as a new person.

```sql
-- WRONG: counts orders, mislabeled as customers
SELECT COUNT(DISTINCT customer_id) FROM customers;        -- 99,441

-- RIGHT: counts actual people
SELECT COUNT(DISTINCT customer_unique_id) FROM customers; -- 96,096
```

### 2. `order_status` has 8 values, not just "delivered/canceled"
Verified breakdown:
| status | count |
|---|---|
| delivered | 96,478 |
| shipped | 1,107 |
| canceled | 625 |
| unavailable | 609 |
| invoiced | 314 |
| processing | 301 |
| created | 5 |
| approved | 2 |

Don't assume "not delivered" means "canceled" — there are 6 other non-delivered states.

### 3. NULLs are not clean or predictable
| Field | NULL count | Notes |
|---|---|---|
| `order_approved_at` | 160 total | 141 canceled, 5 created, **14 delivered** — yes, 14 delivered orders have no recorded approval timestamp. This is real dirty data, not a logic rule. |
| `order_delivered_carrier_date` | 1,783 | |
| `order_delivered_customer_date` | 2,965 | |
| `product_category_name` | 610 products | no category assigned |

Never assume a status implies a field is populated. Use `IS NOT NULL` checks or `LEFT JOIN`, not status-based assumptions, when the query depends on a specific date/category field being present.

### 4. Orders can have multiple items and multiple payments
- 9,803 orders have more than one line item — **SUM `price`** across `order_items` before calling something "order total," don't take `price` from a single row.
- 2,961 orders have split payments (more than one row in `order_payments`) — **SUM `payment_value`** grouped by `order_id` for total paid.

### 5. Not every order has a review
768 orders have no matching row in `order_reviews`. Use LEFT JOIN when the question needs all orders regardless of review status; INNER JOIN silently drops those 768.

### 6. Product categories are in Portuguese
`products.product_category_name` is Portuguese (e.g. `beleza_saude`). Join to `product_category_name_translation` for English (`health_beauty`). If a question asks about categories by name in English, you likely need this join — don't guess a Portuguese term.

**Trap found during benchmark testing:** 2 category names used in `products` have no matching row in the translation table (`pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos`) — 71 translated categories vs 73 actual categories in `products`. If you `LEFT JOIN` to the translation table and then `COUNT(DISTINCT <translated column>)`, these 2 categories silently vanish from the count, because `COUNT(DISTINCT)` ignores NULLs and the translated column is NULL for untranslated categories. The join itself isn't wrong — counting the translated column when you didn't need translation is. For general category-counting questions, count `DISTINCT product_category_name` directly; only join to the translation table when English names are actually needed.

---

## Tables

### `customers`
| Column | Type | Notes |
|---|---|---|
| customer_id | TEXT (PK) | unique per order |
| customer_unique_id | TEXT | shared across a person's repeat orders |
| customer_zip_code_prefix | TEXT | |
| customer_city | TEXT | |
| customer_state | TEXT | 2-letter state code |

### `orders`
| Column | Type | Notes |
|---|---|---|
| order_id | TEXT (PK) | |
| customer_id | TEXT (FK → customers.customer_id) | |
| order_status | TEXT | 8 values — see above, don't assume only 2 |
| order_purchase_timestamp | TEXT (datetime) | no NULLs |
| order_approved_at | TEXT (datetime) | 160 NULLs, not only from canceled orders |
| order_delivered_carrier_date | TEXT (datetime) | 1,783 NULLs |
| order_delivered_customer_date | TEXT (datetime) | 2,965 NULLs |
| order_estimated_delivery_date | TEXT (datetime) | no NULLs |

### `order_items`
| Column | Type | Notes |
|---|---|---|
| order_id | TEXT (FK → orders.order_id) | |
| order_item_id | INTEGER | 1,2,3... within an order |
| product_id | TEXT (FK → products.product_id) | |
| seller_id | TEXT (FK → sellers.seller_id) | |
| shipping_limit_date | TEXT (datetime) | |
| price | REAL | per item, excludes freight |
| freight_value | REAL | per item shipping cost |

> Revenue questions: default to `SUM(price)` (product revenue) unless the user specifies freight should be included. State the assumption in the output.

### `products`
| Column | Type | Notes |
|---|---|---|
| product_id | TEXT (PK) | |
| product_category_name | TEXT | Portuguese, 610 NULLs, join translation table for English |
| product_name_lenght | INTEGER | (sic — typo in source data, kept as-is) |
| product_description_lenght | INTEGER | (sic) |
| product_photos_qty | INTEGER | |
| product_weight_g | INTEGER | |
| product_length_cm | INTEGER | |
| product_height_cm | INTEGER | |
| product_width_cm | INTEGER | |

### `product_category_name_translation`
| Column | Type | Notes |
|---|---|---|
| product_category_name | TEXT | Portuguese, join key to products |
| product_category_name_english | TEXT | English name |

### `sellers`
| Column | Type | Notes |
|---|---|---|
| seller_id | TEXT (PK) | |
| seller_zip_code_prefix | TEXT | |
| seller_city | TEXT | |
| seller_state | TEXT | |

### `order_payments`
| Column | Type | Notes |
|---|---|---|
| order_id | TEXT (FK → orders.order_id) | |
| payment_sequential | INTEGER | 1,2,3... if split |
| payment_type | TEXT | credit_card / boleto / voucher / debit_card |
| payment_installments | INTEGER | |
| payment_value | REAL | this payment row's amount, SUM per order_id for total |

### `order_reviews`
| Column | Type | Notes |
|---|---|---|
| review_id | TEXT (PK) | |
| order_id | TEXT (FK → orders.order_id) | 768 orders have no matching review |
| review_score | INTEGER | 1-5 |
| review_comment_title | TEXT | often NULL |
| review_comment_message | TEXT | often NULL |
| review_creation_date | TEXT (datetime) | |
| review_answer_timestamp | TEXT (datetime) | |

---

## Relationships (for JOINs)

```
customers.customer_id                    = orders.customer_id
orders.order_id                          = order_items.order_id
orders.order_id                          = order_payments.order_id
orders.order_id                          = order_reviews.order_id
order_items.product_id                   = products.product_id
order_items.seller_id                    = sellers.seller_id
products.product_category_name           = product_category_name_translation.product_category_name
```

## Indexes (already created)
FK columns are indexed: `orders.customer_id`, `order_items.order_id/product_id/seller_id`,
`order_payments.order_id`, `order_reviews.order_id`, `customers.customer_unique_id`.
At 99K+ rows, unindexed joins will be noticeably slower — this matters for the
Day 3-4 timeout guard, not just theoretically.

## Row-limit / timeout guards (enforced at execution layer)
- Max rows returned: 1000 (auto LIMIT injected if missing)
- Query timeout: 10 seconds
- At this scale (99K orders, 112K order items), an unbounded query without WHERE/LIMIT
  on a cross join could genuinely hang — the guard is now doing real work, not a formality.

## Table sizes (verified)
| Table | Rows |
|---|---|
| customers | 99,441 |
| orders | 99,441 |
| order_items | 112,650 |
| order_payments | 103,886 |
| order_reviews | 99,224 |
| products | 32,951 |
| sellers | 3,095 |
| product_category_name_translation | 71 |
