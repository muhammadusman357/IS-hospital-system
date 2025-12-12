# 🏥 Hospital Management System – Privacy-Centric Dashboard

[![Python](https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.30-orange?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License](https://img.shields.io/badge/license-Educational-green)](#)

**Course:** Information Security (CS-3002)  
**Assignment:** #4 – Privacy, Trust & the CIA Triad in Modern Information Systems  
**Team:** 2 Members  

---

## 📖 Overview

This is a **GDPR-compliant mini hospital management system** developed using **Streamlit, Python, and SQLite**.  
It demonstrates the implementation of the **CIA triad** (Confidentiality, Integrity, Availability) while ensuring **privacy, auditability, and system reliability**.

The system allows hospital staff to securely manage patient data with:

- Role-based access control (**RBAC**)  
- Data anonymization/masking  
- Secure logging of user actions  

---

## ✨ Features

### 🔒 Confidentiality (Data Protection & Privacy)
- Personal patient data is **anonymized or encrypted** using `hashlib` or optionally **Fernet encryption** for reversible anonymization.  
- Sensitive fields are masked:
  - Name → `ANON_1021`  
  - Contact → `XXX-XXX-4592`  
- **Role-Based Access Control (RBAC):**
  - **Admin:** Full access to raw & anonymized data  
  - **Doctor:** Access to anonymized data only  
  - **Receptionist:** Add/edit records but cannot view sensitive data  
- Secure **login page** ensures user authentication  

### 📝 Integrity (Data Accuracy & Accountability)
- **Activity logs** track every action:
  - Role, timestamp, action type, and details  
- Database constraints prevent unauthorized changes  
- Admin-only **Integrity Audit Log** display  

### ⚡ Availability (System Access & Reliability)
- Dashboard and database remain responsive  
- **Error handling** for failed logins or DB issues  
- **Data backup/export** for recovery  
- Footer shows **system uptime / last synchronization**  

---

## 💾 Database Schema

### `users` Table
| user_id | username     | password   | role        |
|---------|-------------|------------|------------|
| 1       | admin       | admin123   | admin      |
| 2       | Dr. Bob     | doc123     | doctor     |
| 3       | Alice_recep | rec123     | receptionist |

### `patients` Table
| patient_id | name | contact | diagnosis | anonymized_name | anonymized_contact | date_added |

### `logs` Table
| log_id | user_id | role | action | timestamp | details |

---

## 🏃‍♂️ Example Workflow

1. User logs in → credentials verified → role assigned  
2. Role defines permitted actions (RBAC)  
3. Admin triggers **“Anonymize Data”** → sensitive fields masked/encrypted  
4. Doctor views anonymized patient data  
5. Receptionist adds/edits records but cannot see masked data  
6. All actions timestamped and stored in logs  
7. Admin reviews audit logs and exports securely  

---

## 📂 Project Structure

```text
hospital_system/
├─ app.py                 # Main Streamlit app
├─ core/                  # Core modules (auth, database, encryption, logging, validation)
├─ pages/                 # Streamlit pages (login, dashboards)
├─ data/                  # Database & backups (LOCAL ONLY)
├─ requirements.txt       # Python dependencies
├─ .gitignore             # Ignored files (.env, DB, backups)
└─ README.md
