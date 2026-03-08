import React, { useState, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { FileText, AlertTriangle } from 'lucide-react';

export const TermsModal = ({ isOpen, onAccept }) => {
  const [agreed, setAgreed] = useState(false);
  const [scrolledToBottom, setScrolledToBottom] = useState(false);
  const scrollRef = useRef(null);

  const handleScroll = (e) => {
    const element = e.target;
    const isAtBottom = element.scrollHeight - element.scrollTop <= element.clientHeight + 50;
    if (isAtBottom) {
      setScrolledToBottom(true);
    }
  };

  const handleAccept = () => {
    if (agreed) {
      onAccept();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={() => {}}>
      <DialogContent className="sm:max-w-4xl bg-slate-800 border-slate-700 max-h-[95vh] overflow-hidden" hideCloseButton>
        <DialogHeader>
          <DialogTitle className="text-white text-2xl flex items-center gap-2">
            <FileText className="w-6 h-6 text-blue-400" />
            Terms of Service
          </DialogTitle>
        </DialogHeader>

        <Alert className="bg-yellow-900/20 border-yellow-700 text-yellow-300 mb-4">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Please read and scroll through the entire Terms of Service before accepting.
          </AlertDescription>
        </Alert>

        <ScrollArea 
          className="h-[50vh] pr-4 border border-slate-700 rounded-lg"
          onScrollCapture={handleScroll}
          ref={scrollRef}
        >
          <div className="p-4 text-gray-300 text-sm space-y-6">
            <h2 className="text-xl font-bold text-white">Crypto Bag Tracker Terms of Service</h2>
            
            <section>
              <h3 className="text-lg font-semibold text-white mb-2">1. Acceptance of Terms</h3>
              <p>By accessing, browsing, creating an account, clicking "I agree", using any analysis feature, or otherwise using Crypto Bag Tracker (the "Platform"), you acknowledge that you have read, understood, and agree to be bound by these Terms of Service (the "Terms"), as well as our Privacy Policy.</p>
              <p className="mt-2">If you do not agree to these Terms, you must not access or use the Platform.</p>
              <p className="mt-2">If you are using the Platform on behalf of a company, organization, or other legal entity, you represent and warrant that you have the authority to bind that entity to these Terms, and "you" and "your" will refer to both you and that entity.</p>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">2. Eligibility</h3>
              <p>You must be at least 18 years old, or the age of legal majority in your jurisdiction, whichever is greater, to use the Platform.</p>
              <p className="mt-2">By using the Platform, you represent and warrant that:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>you meet the applicable age requirement;</li>
                <li>you have the legal capacity to enter into these Terms; and</li>
                <li>your use of the Platform does not violate any applicable law, regulation, or contractual obligation.</li>
              </ul>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">3. Description of the Platform</h3>
              <p>Crypto Bag Tracker is a read-only informational analytics platform that analyzes publicly available blockchain wallet and transaction data across supported blockchain networks.</p>
              <p className="mt-2">The Platform may provide, without limitation:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>wallet activity summaries;</li>
                <li>token and transaction histories;</li>
                <li>labels, classifications, inferences, or analytics;</li>
                <li>historical views based on selected dates; and</li>
                <li>other blockchain-related informational outputs.</li>
              </ul>
              <p className="mt-2">The Platform is provided for informational and analytical purposes only. Crypto Bag Tracker does not hold, custody, control, transmit, or manage digital assets on your behalf, does not execute transactions, and does not access private keys or seed phrases.</p>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">4. No Financial, Legal, Tax, or Professional Advice</h3>
              <p className="font-semibold text-yellow-400">The Platform and all content, data, analytics, labels, classifications, reports, and outputs made available through the Platform are provided for informational purposes only.</p>
              <p className="mt-2">Crypto Bag Tracker does not provide:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>financial or investment advice;</li>
                <li>legal advice;</li>
                <li>tax advice;</li>
                <li>accounting advice; or</li>
                <li>any other professional advice.</li>
              </ul>
              <p className="mt-2">Nothing on the Platform constitutes a recommendation, solicitation, endorsement, or instruction to buy, sell, hold, transfer, report, classify, or otherwise take action with respect to any digital asset, wallet, address, transaction, or blockchain activity.</p>
              <p className="mt-2 font-semibold text-yellow-400">You are solely responsible for independently verifying all information and consulting qualified professionals before making any decision based on the Platform.</p>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">5. Data Accuracy and No Reliance</h3>
              <p>You acknowledge and agree that blockchain analytics can be inherently uncertain and that the Platform's outputs are provided on a best-effort basis only.</p>
              <p className="mt-2">Without limiting the foregoing, the Platform's outputs may be:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>incomplete;</li>
                <li>delayed;</li>
                <li>inaccurate;</li>
                <li>unreliable;</li>
                <li>outdated;</li>
                <li>based on assumptions or heuristics; or</li>
                <li>unable to capture all relevant cross-chain or off-chain activity.</li>
              </ul>
              <p className="mt-2">Wallet ownership, transaction purpose, asset classification, and related inferences may not be determinable with certainty.</p>
              <p className="mt-2">You agree that:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>you will not rely exclusively on the Platform for any financial, legal, tax, compliance, investigative, or business decision;</li>
                <li>you are solely responsible for independently verifying any information obtained through the Platform; and</li>
                <li>any use of or reliance on the Platform is entirely at your own risk.</li>
              </ul>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">6. Accounts and Access</h3>
              <p>To access certain features, you may be required to create an account.</p>
              <p className="mt-2">You agree to:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>provide accurate, current, and complete registration information;</li>
                <li>maintain and promptly update your information;</li>
                <li>maintain the confidentiality of your login credentials; and</li>
                <li>accept responsibility for all activities that occur under your account.</li>
              </ul>
              <p className="mt-2">You must notify us immediately of any unauthorized access to or use of your account.</p>
              <p className="mt-2">We reserve the right to suspend, restrict, or terminate your account at any time, with or without notice, if we believe you have violated these Terms or that your use of the Platform presents legal, security, or operational risk.</p>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">7. Acceptable Use</h3>
              <p>You agree not to, and not to permit any third party to:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>use the Platform for any unlawful, fraudulent, deceptive, or abusive purpose;</li>
                <li>use the Platform to violate any law, regulation, or third-party right;</li>
                <li>misuse, overload, scrape, crawl, mirror, reverse engineer, decompile, disassemble, or otherwise attempt to derive source code from the Platform;</li>
                <li>interfere with or disrupt the integrity, security, or performance of the Platform;</li>
                <li>use automated tools, bots, or scripts to access the Platform in a manner that exceeds normal human usage;</li>
                <li>attempt to bypass authentication, access controls, or usage restrictions;</li>
                <li>use the Platform to harass, defame, stalk, dox, or target any individual or entity;</li>
                <li>use the Platform to facilitate fraud, sanctions evasion, money laundering, hacking, phishing, or other illicit conduct;</li>
                <li>misrepresent the Platform's outputs as certified, guaranteed, legally binding, or professionally verified;</li>
                <li>remove, alter, or obscure any proprietary notices; or</li>
                <li>use the Platform in a way that could damage, disable, or impair the Platform or our systems.</li>
              </ul>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">8. User Inputs and Responsibility</h3>
              <p>You are solely responsible for any wallet addresses, dates, information, or other inputs you submit into the Platform.</p>
              <p className="mt-2">You represent and warrant that:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>you have the right to input and use any information you provide;</li>
                <li>your inputs do not violate any law or third-party right; and</li>
                <li>you will not submit malicious code, harmful data, or unlawful content.</li>
              </ul>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">9. Intellectual Property</h3>
              <p>The Platform, including all software, code, design, text, graphics, interfaces, trademarks, service marks, logos, databases, and other content, is owned by or licensed to Crypto Bag Tracker and is protected by intellectual property and other applicable laws.</p>
              <p className="mt-2">Subject to your compliance with these Terms, we grant you a limited, non-exclusive, non-transferable, revocable license to access and use the Platform for its intended purpose.</p>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">10. Third-Party Services and Data Sources</h3>
              <p>The Platform may rely on or integrate with third-party services, APIs, infrastructure providers, data sources, or blockchain indexers.</p>
              <p className="mt-2">We do not control and are not responsible for:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>the availability, accuracy, timeliness, legality, or completeness of third-party services or data;</li>
                <li>outages, delays, or failures caused by third parties; or</li>
                <li>any losses arising from your use of or reliance on third-party content or services.</li>
              </ul>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">11. Fees and Payments</h3>
              <p>If the Platform offers paid subscriptions, premium features, usage-based billing, or other paid services, you agree to pay all applicable fees as described at the time of purchase.</p>
              <p className="mt-2">Unless otherwise stated:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>all fees are quoted in USD;</li>
                <li>fees are non-refundable except as required by law or expressly stated by us;</li>
                <li>subscriptions may renew automatically unless canceled before the renewal date; and</li>
                <li>you authorize us and our payment processors to charge your selected payment method for all applicable fees, taxes, and charges.</li>
              </ul>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">12. Disclaimer of Warranties</h3>
              <p className="font-semibold text-red-400">TO THE FULLEST EXTENT PERMITTED BY LAW, THE PLATFORM IS PROVIDED "AS IS," "AS AVAILABLE," AND "WITH ALL FAULTS."</p>
              <p className="mt-2">CRYPTO BAG TRACKER DISCLAIMS ALL WARRANTIES, EXPRESS, IMPLIED, STATUTORY, OR OTHERWISE, INCLUDING WITHOUT LIMITATION:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1 text-red-300">
                <li>WARRANTIES OF MERCHANTABILITY;</li>
                <li>FITNESS FOR A PARTICULAR PURPOSE;</li>
                <li>TITLE;</li>
                <li>NON-INFRINGEMENT;</li>
                <li>ACCURACY;</li>
                <li>COMPLETENESS;</li>
                <li>RELIABILITY;</li>
                <li>AVAILABILITY;</li>
                <li>SECURITY; AND</li>
                <li>THAT THE PLATFORM WILL BE ERROR-FREE, UNINTERRUPTED, OR FREE OF HARMFUL COMPONENTS.</li>
              </ul>
              <p className="mt-2">WITHOUT LIMITING THE FOREGOING, WE MAKE NO REPRESENTATION OR WARRANTY THAT:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>ANY DATA, OUTPUT, LABEL, CLASSIFICATION, OR ANALYSIS IS ACCURATE OR COMPLETE;</li>
                <li>THE PLATFORM WILL MEET YOUR REQUIREMENTS;</li>
                <li>THE PLATFORM IS SUITABLE FOR TAX, LEGAL, COMPLIANCE, OR INVESTMENT USE;</li>
                <li>ANY ERRORS OR DEFECTS WILL BE CORRECTED; OR</li>
                <li>ANY PARTICULAR RESULT OR OUTCOME WILL BE ACHIEVED THROUGH USE OF THE PLATFORM.</li>
              </ul>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">13. Limitation of Liability</h3>
              <p className="text-red-400">TO THE FULLEST EXTENT PERMITTED BY LAW, CRYPTO BAG TRACKER AND ITS OWNERS, OFFICERS, DIRECTORS, EMPLOYEES, CONTRACTORS, AFFILIATES, LICENSORS, AND SERVICE PROVIDERS SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE DAMAGES, OR FOR ANY LOSS OF PROFITS, REVENUE, BUSINESS, GOODWILL, DATA, USE, DIGITAL ASSETS, OR OTHER INTANGIBLE LOSSES.</p>
              <p className="mt-2">TO THE FULLEST EXTENT PERMITTED BY LAW, OUR TOTAL AGGREGATE LIABILITY FOR ALL CLAIMS ARISING OUT OF OR RELATING TO THESE TERMS OR THE PLATFORM SHALL NOT EXCEED THE GREATER OF:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>THE AMOUNT YOU PAID TO US FOR USE OF THE PLATFORM IN THE TWELVE (12) MONTHS PRECEDING THE EVENT GIVING RISE TO THE CLAIM; OR</li>
                <li>ONE HUNDRED U.S. DOLLARS (US $100).</li>
              </ul>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">14. Indemnification</h3>
              <p>You agree to defend, indemnify, and hold harmless Crypto Bag Tracker and its owners, officers, directors, employees, contractors, affiliates, licensors, service providers, and agents from and against any and all claims, demands, actions, proceedings, liabilities, damages, losses, judgments, settlements, penalties, fines, costs, and expenses (including reasonable attorneys' fees) arising out of or relating to:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>your use of or reliance on the Platform;</li>
                <li>your violation of these Terms;</li>
                <li>your misuse of the Platform;</li>
                <li>your violation of any law, regulation, or third-party right;</li>
                <li>any information, wallet address, data, or content you submit or use in connection with the Platform; or</li>
                <li>any claim by a third party arising from your actions, omissions, or use of the Platform.</li>
              </ul>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">15. Termination</h3>
              <p>We may suspend, restrict, or terminate your access to the Platform, in whole or in part, at any time, with or without notice, for any reason, including if we believe you have violated these Terms, created legal or security risk, or used the Platform in a manner that may harm us, other users, or third parties.</p>
              <p className="mt-2">You may stop using the Platform at any time.</p>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">16. Dispute Resolution; Arbitration; Class Action Waiver</h3>
              <p>To the fullest extent permitted by law, you and Crypto Bag Tracker agree that any dispute, claim, or controversy arising out of or relating to these Terms or the Platform shall first be attempted to be resolved informally by contacting the other party in writing.</p>
              <p className="mt-2">If the dispute is not resolved informally within thirty (30) days, the dispute shall be resolved by binding arbitration on an individual basis.</p>
              <p className="mt-2 font-semibold text-yellow-400">You and Crypto Bag Tracker each agree that claims will be brought only in an individual capacity and not as a plaintiff or class member in any purported class, collective, representative, or private attorney general proceeding, and you waive any right to participate in a class action, collective action, or representative action.</p>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">17. Governing Law and Venue</h3>
              <p>These Terms and any dispute arising out of or relating to these Terms or the Platform shall be governed by the laws of the State of Texas, without regard to its conflict of laws principles.</p>
              <p className="mt-2">To the extent any dispute is permitted to proceed in court rather than arbitration, you agree that such dispute shall be brought exclusively in the state or federal courts located in Travis County, Texas, and you consent to the personal jurisdiction and venue of those courts.</p>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">18. Changes to These Terms</h3>
              <p>We may modify these Terms at any time in our sole discretion.</p>
              <p className="mt-2">Your continued use of the Platform after the updated Terms become effective constitutes your acceptance of the revised Terms.</p>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">19. Miscellaneous</h3>
              <p>These Terms constitute the entire agreement between you and Crypto Bag Tracker regarding the Platform and supersede all prior or contemporaneous understandings relating to the subject matter herein.</p>
              <p className="mt-2">If any provision of these Terms is held invalid, illegal, or unenforceable, the remaining provisions will remain in full force and effect.</p>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white mb-2">20. Contact Information</h3>
              <p>If you have questions about these Terms, please contact Crypto Bag Tracker through the support channels provided on the Platform.</p>
            </section>

            <div className="h-8"></div>
          </div>
        </ScrollArea>

        <div className="space-y-4 pt-4">
          <div className="flex items-start space-x-3 p-4 bg-slate-900/50 rounded-lg border border-slate-700">
            <Checkbox 
              id="terms-agreement" 
              checked={agreed}
              onCheckedChange={setAgreed}
              className="mt-1 border-slate-500 data-[state=checked]:bg-blue-600"
              data-testid="terms-checkbox"
            />
            <label 
              htmlFor="terms-agreement" 
              className="text-sm text-gray-300 cursor-pointer leading-relaxed"
            >
              I have read and agree to the <span className="text-blue-400 font-semibold">Terms of Service</span>, <span className="text-blue-400 font-semibold">Privacy Policy</span>, and <span className="text-blue-400 font-semibold">Disclaimer</span>, and I understand that Crypto Bag Tracker provides informational blockchain analytics only, on a best-effort basis, with <span className="text-yellow-400 font-semibold">no guarantee of accuracy or completeness</span>.
            </label>
          </div>

          <Button
            onClick={handleAccept}
            disabled={!agreed}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-500 h-12 text-lg"
            data-testid="accept-terms-btn"
          >
            {agreed ? 'I Accept - Continue to Crypto Bag Tracker' : 'Please read and accept the Terms of Service'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
