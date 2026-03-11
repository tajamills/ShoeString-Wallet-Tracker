# Crypto Bag Tracker - Risk Assessment

## Purpose

This document provides a comprehensive risk assessment for insurance underwriting purposes. It identifies potential risks, their likelihood, impact, and mitigation strategies.

---

## 1. Business Overview

| Attribute | Details |
|-----------|---------|
| Business Type | SaaS (Software as a Service) |
| Industry | FinTech / Cryptocurrency Tax Software |
| Revenue Model | Annual subscriptions ($100.88/year) |
| Target Market | US cryptocurrency holders |
| Data Handled | Financial data, wallet addresses, transaction history |

---

## 2. Risk Categories

### 2.1 Cyber Security Risks

#### 2.1.1 Data Breach
| Attribute | Assessment |
|-----------|------------|
| Likelihood | Low |
| Impact | High |
| Risk Level | Medium |

**Description:** Unauthorized access to user data including email addresses, wallet addresses, and transaction history.

**Mitigations:**
- All data encrypted at rest and in transit
- Database hosted on SOC 2 certified platform (MongoDB Atlas)
- Access controls and audit logging
- No storage of private keys or seed phrases
- Regular security reviews

**Residual Risk:** Low - Strong encryption and access controls significantly reduce breach likelihood.

---

#### 2.1.2 API Key Exposure
| Attribute | Assessment |
|-----------|------------|
| Likelihood | Low |
| Impact | Medium |
| Risk Level | Low-Medium |

**Description:** User-provided exchange API keys could be compromised.

**Mitigations:**
- API keys encrypted with AES-128 (Fernet)
- Encryption key stored in environment variables
- Read-only API permissions only
- Keys cannot move or withdraw funds
- Users can revoke keys at any time

**Residual Risk:** Low - Even if exposed, keys are read-only and cannot transfer funds.

---

#### 2.1.3 Service Unavailability (DDoS)
| Attribute | Assessment |
|-----------|------------|
| Likelihood | Low |
| Impact | Medium |
| Risk Level | Low |

**Description:** Distributed denial of service attack makes the platform unavailable.

**Mitigations:**
- Cloud hosting with DDoS protection (Render)
- Rate limiting on all endpoints
- Scalable infrastructure

**Residual Risk:** Low - Cloud platform handles most DDoS mitigation automatically.

---

### 2.2 Operational Risks

#### 2.2.1 Third-Party API Failure
| Attribute | Assessment |
|-----------|------------|
| Likelihood | Medium |
| Impact | Medium |
| Risk Level | Medium |

**Description:** Blockchain APIs (Alchemy, Blockstream) or price APIs (CoinGecko) become unavailable.

**Mitigations:**
- Fallback pricing for rate limiting
- Multiple blockchain data providers
- Graceful error handling
- User notification of data issues

**Residual Risk:** Medium - Some dependency on third parties, but fallbacks in place.

---

#### 2.2.2 Incorrect Tax Calculations
| Attribute | Assessment |
|-----------|------------|
| Likelihood | Low |
| Impact | Medium |
| Risk Level | Medium |

**Description:** Software produces incorrect tax calculations leading to user tax issues.

**Mitigations:**
- Clear disclaimers that output is estimates only
- Recommendation to consult CPA
- FIFO method follows IRS guidelines
- Export data for professional review
- No guarantee of accuracy in Terms of Service

**Residual Risk:** Low - Disclaimers and Terms of Service limit liability.

---

#### 2.2.3 Data Loss
| Attribute | Assessment |
|-----------|------------|
| Likelihood | Very Low |
| Impact | High |
| Risk Level | Low |

**Description:** User data is permanently lost due to system failure.

**Mitigations:**
- Continuous database backups (MongoDB Atlas)
- Point-in-time recovery capability
- 30-day backup retention
- Multi-region database replication

**Residual Risk:** Very Low - Robust backup and recovery systems.

---

### 2.3 Financial Risks

#### 2.3.1 User Funds Loss
| Attribute | Assessment |
|-----------|------------|
| Likelihood | Very Low |
| Impact | Critical |
| Risk Level | Very Low |

**Description:** Users lose cryptocurrency funds due to our platform.

**Mitigations:**
- **READ-ONLY ACCESS ONLY** - Platform cannot move funds
- No private keys ever stored or requested
- No withdrawal capability
- All exchange connections are read-only
- Clear communication of read-only nature

**Residual Risk:** Very Low - Architecturally impossible to move user funds.

---

#### 2.3.2 Payment Fraud
| Attribute | Assessment |
|-----------|------------|
| Likelihood | Low |
| Impact | Low |
| Risk Level | Low |

**Description:** Fraudulent payments or chargebacks.

**Mitigations:**
- Stripe handles all payment processing
- Stripe fraud detection
- No direct card data handling
- Subscription model reduces fraud incentive

**Residual Risk:** Low - Stripe absorbs most payment fraud risk.

---

### 2.4 Legal & Regulatory Risks

#### 2.4.1 Regulatory Changes
| Attribute | Assessment |
|-----------|------------|
| Likelihood | Medium |
| Impact | Medium |
| Risk Level | Medium |

**Description:** IRS or other regulators change cryptocurrency tax rules.

**Mitigations:**
- Flexible tax calculation engine
- Regular monitoring of regulatory changes
- Ability to update calculation methods
- Disclaimers about following current guidance

**Residual Risk:** Medium - Some regulatory uncertainty in crypto space.

---

#### 2.4.2 Privacy Violations
| Attribute | Assessment |
|-----------|------------|
| Likelihood | Low |
| Impact | High |
| Risk Level | Low-Medium |

**Description:** Violation of CCPA, GDPR, or other privacy regulations.

**Mitigations:**
- Privacy Policy in place
- Data deletion capability
- No data selling
- Minimal data collection
- User consent for data processing

**Residual Risk:** Low - Standard privacy practices in place.

---

#### 2.4.3 Professional Liability Claims
| Attribute | Assessment |
|-----------|------------|
| Likelihood | Low |
| Impact | Medium |
| Risk Level | Low-Medium |

**Description:** Users claim damages due to reliance on tax calculations.

**Mitigations:**
- Clear disclaimers throughout application
- Terms of Service limit liability
- Recommendation to consult professionals
- "Estimates only" language
- Limitation of liability clause

**Residual Risk:** Low - Strong disclaimers and liability limitations.

---

### 2.5 Reputational Risks

#### 2.5.1 Negative Reviews / Press
| Attribute | Assessment |
|-----------|------------|
| Likelihood | Medium |
| Impact | Low-Medium |
| Risk Level | Low |

**Description:** Negative publicity due to bugs, outages, or user complaints.

**Mitigations:**
- Quality assurance processes
- Responsive customer support
- AI support assistant for quick help
- Bug fix prioritization

**Residual Risk:** Low - Standard business risk.

---

## 3. Risk Matrix Summary

| Risk | Likelihood | Impact | Risk Level |
|------|------------|--------|------------|
| Data Breach | Low | High | Medium |
| API Key Exposure | Low | Medium | Low-Medium |
| DDoS Attack | Low | Medium | Low |
| API Failure | Medium | Medium | Medium |
| Incorrect Calculations | Low | Medium | Medium |
| Data Loss | Very Low | High | Low |
| **User Funds Loss** | **Very Low** | **Critical** | **Very Low** |
| Payment Fraud | Low | Low | Low |
| Regulatory Changes | Medium | Medium | Medium |
| Privacy Violations | Low | High | Low-Medium |
| Professional Liability | Low | Medium | Low-Medium |
| Reputation Damage | Medium | Low-Medium | Low |

---

## 4. Key Risk Mitigations Summary

### Critical Controls

1. **Read-Only Architecture**
   - All exchange connections are read-only
   - No ability to move, send, or withdraw funds
   - No private key storage

2. **Data Encryption**
   - All data encrypted at rest (AES-128)
   - All data encrypted in transit (TLS 1.3)
   - Passwords hashed with bcrypt

3. **Third-Party Security**
   - SOC 2 certified hosting (Render)
   - SOC 2 certified database (MongoDB Atlas)
   - PCI DSS certified payments (Stripe)

4. **Liability Limitations**
   - Clear Terms of Service
   - Tax calculation disclaimers
   - Professional consultation recommendations
   - Limitation of liability clauses

---

## 5. Insurance Recommendations

### Recommended Coverage

| Coverage Type | Reason | Suggested Limit |
|---------------|--------|-----------------|
| Cyber Liability | Data breach, cyber attacks | $1-2 million |
| E&O / Professional Liability | Incorrect calculations, advice | $1 million |
| General Liability | Standard business operations | $1 million |
| Business Interruption | Service outages | Based on revenue |

### Coverage Notes

- **Cyber Liability** - Primary concern given digital nature of business
- **E&O** - Important due to tax calculation feature
- **General Liability** - Standard coverage
- **D&O** - If applicable based on corporate structure

---

## 6. Conclusion

Crypto Bag Tracker presents a **low to medium overall risk profile** for the following reasons:

1. **No Custody of Funds** - Most critical: we cannot move user cryptocurrency
2. **Read-Only Access** - All integrations are read-only
3. **Encrypted Data** - Sensitive data protected at rest and in transit
4. **Established Infrastructure** - Using proven, certified cloud providers
5. **Clear Disclaimers** - Legal protections in place for tax calculations

The most significant liability exposure is professional liability related to tax calculations, which is mitigated through disclaimers and Terms of Service.

---

## 7. Contact

For questions regarding this risk assessment:

**Email:** support@cryptobagtracker.com  
**Address:** 1557 Buford Dr #492773, Lawrenceville, GA 30043  
**Website:** https://cryptobagtracker.io

---

*Document Version: 1.0*  
*Last Updated: March 10, 2026*  
*Confidential - For Insurance Underwriting Purposes*
