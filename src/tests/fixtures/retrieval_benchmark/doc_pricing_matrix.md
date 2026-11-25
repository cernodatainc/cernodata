# Halvorsen Data Systems: Stratus Object Storage Price List

Issued by the Halvorsen Commercial Office, Bergen. This edition supersedes all earlier Stratus price lists and applies to new and renewing subscriptions.

## Overview

Stratus Object Storage is billed per terabyte (TB) of stored data per month, measured as the average daily volume across the billing period. Prices below are list prices before volume discounts and sales taxes. Each region is invoiced in its local settlement currency, shown in the column header.

## Storage Price Matrix

All prices are per TB per month.

| Tier | North America (USD) | European Union (EUR) | United Kingdom (GBP) | Asia-Pacific (USD) | Latin America (USD) |
|---|---|---|---|---|---|
| Starter | 8.40 | 7.95 | 6.85 | 9.15 | 8.70 |
| Team | 13.20 | 12.50[^1] | 10.75 | 14.05 | 13.60 |
| Business | 18.30 | 17.45 | 15.10 | 19.80 | 18.95 |
| Enterprise[^3] | 24.60 | 23.35[^2] | 20.40 | 26.25 | 25.10 |
| Archive | 2.15 | 1.98 | 1.72 | 2.44 | 2.31 |

## Tier Descriptions

- **Starter:** single namespace, community forum support, capacity cap of 16 TB.
- **Team:** shared access policies, business-hours support, capacity cap of 120 TB.
- **Business:** cross-region replication, round-the-clock support, capacity cap of 900 TB.
- **Enterprise:** named account manager, customer-managed encryption keys, no capacity cap.
- **Archive:** cold storage for compliance retention; see Archive Tier Terms below.

## Volume Discounts

Accounts whose month-end stored volume exceeds 650 TB receive a 6 percent discount on the storage line of the invoice. Accounts above 2,400 TB receive a 17 percent discount instead. Discounts do not apply to data transfer or request charges.

## Data Transfer and Request Charges

These charges are identical in every region and are always billed in USD.

| Charge | Unit | Price (USD) |
|---|---|---|
| Internet egress | per GB | 0.068 |
| Inter-region replication | per GB | 0.032 |
| Write and list requests | per thousand | 0.0047 |
| Read requests | per thousand | 0.00041 |

## Archive Tier Terms

Restore requests for Archive objects complete within 14 hours. Objects deleted early are charged for the remaining days of the commitment period. The minimum commitment for Archive storage is 9 months per object.

[^1]: Effective Q3, the EU price for the Team tier is 11.90.
[^2]: EU Enterprise contracts signed under the previous price list keep a grandfathered rate of 22.80 until their next renewal.
[^3]: Minimum commitment of 36 months applies.