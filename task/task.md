### 1. **Contract Enforcer**

- Makes sure every record has the required fields (like CustomerID, FirstName, Email, Phone).
- Drops extra columns that aren’t part of the contract.
- Renames columns if they come in with different names (e.g., “E-mail” → “Email”).
- Casts values into the right type (e.g., numbers vs text).
- Enforces allowed values (e.g., countries must be USA, Canada, UK, Spain, China, UAE).
- Invalid values get replaced with `null` unless told otherwise.

---

### 2. **Semantic Mapper**

- Cleans up messy column names and values.
- Example: “FName” becomes “FirstName”, “U.S.A” becomes “USA”, “Calif.” becomes “CA”.
- Uses similarity, patterns, and value analysis to decide mappings.
- Only applies mappings if confidence is high enough (≥0.7).

---

### 3. **Survivorship Resolver**

- When duplicate records exist, decides which value to keep.
- Uses rules like:
  - **Freshness** → pick the most recent (based on `LastUpdated`).
  - **Frequency** → pick the most common (e.g., phone number).
  - **Completeness** → pick the most detailed address.
  - **Validation** → only keep values that pass rules (valid email, postal code format, allowed country/state).
- If rules tie, falls back to source priority (CRM > ERP > WebPortal > Marketing > Support).

---

### 4. **Golden Record Builder**

- Combines everything into one “best version” of each customer (the golden record).
- Uses survivorship rules to decide which field wins.
- Default rule is “most complete” if nothing else applies.
- Trust scores are calculated; records below 0.5 confidence get flagged.
- Records rated ≥90 are “Excellent”, ≥75 are “Good”.

---

### 5. **Stewardship Flagger**

- Flags records that need human review.
- Checks required fields are filled.
- Validates formats (emails, postal codes, states, countries).
- Detects outliers (e.g., phone numbers too short/long).
- Flags duplicates (same CustomerID or Email).
- Applies business rules (e.g., promo.com emails flagged for review, Support system phone consistency warnings).
- Severity levels (low, medium, high, critical) affect scoring.

---

## 🧪 What You Should See in Testing

- **Clean records** pass through with no flags.
- **Noisy values** (like “U.S.A”, “Calif.”) get normalized.
- **Invalid values** (bad emails, wrong postal codes, unsupported countries) get flagged.
- **Duplicates** collapse into one golden record, keeping the freshest/most complete info.
- **Scores** show overall data quality: Excellent, Good, or Needs Review.
- **Flags** highlight records that require manual stewardship.

---

👉 In short:  
The toolset should **clean, standardize, validate, merge, and score** customer records, producing a single trusted “golden record” per customer while flagging anything suspicious for human review.
AI Video Maker - Create Videos with AI Technology - https://promo.com
Leverage AI technology to make stunning videos in minutes with our AI video maker. Start creating innovative content today with ease!
