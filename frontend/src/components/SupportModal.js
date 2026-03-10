/**
 * Support Modal Component v2.1
 * Provides contact form and AI-powered help for users.
 * Last updated: Mar 10, 2026 - Mobile responsive
 */
import React, { useState, useRef, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  MessageCircle,
  Send,
  Mail,
  Bot,
  User,
  Loader2,
  CheckCircle2,
  HelpCircle,
  X
} from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const SupportModal = ({ isOpen, onClose, getAuthHeader, isLoggedIn }) => {
  const [activeTab, setActiveTab] = useState('ai'); // 'ai' or 'contact'
  
  // AI Chat state
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestedQuestions, setSuggestedQuestions] = useState([]);
  
  // Contact form state
  const [contactForm, setContactForm] = useState({
    name: '',
    email: '',
    subject: '',
    message: ''
  });
  const [contactSubmitted, setContactSubmitted] = useState(false);
  const [contactError, setContactError] = useState('');
  
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (isOpen && isLoggedIn) {
      fetchSuggestedQuestions();
    }
  }, [isOpen, isLoggedIn]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchSuggestedQuestions = async () => {
    try {
      const response = await axios.get(`${API}/support/suggested-questions`);
      setSuggestedQuestions(response.data.questions || []);
    } catch (err) {
      console.error('Failed to fetch suggested questions');
    }
  };

  const sendMessage = async (messageText = null) => {
    const text = messageText || inputMessage.trim();
    if (!text || loading) return;

    // Add user message
    const userMessage = { role: 'user', content: text };
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setLoading(true);

    try {
      const response = await axios.post(
        `${API}/support/ai-chat`,
        {
          message: text,
          conversation_history: messages.slice(-10)
        },
        { headers: getAuthHeader() }
      );

      if (response.data.success) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: response.data.response
        }]);
      } else {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: response.data.response || 'Sorry, I encountered an error. Please try again.'
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Unable to connect to support. Please try again or email support@cryptobagtracker.io'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const submitContactForm = async () => {
    setContactError('');
    
    if (!contactForm.name || !contactForm.email || !contactForm.message) {
      setContactError('Please fill in all required fields');
      return;
    }

    setLoading(true);
    try {
      await axios.post(`${API}/support/contact`, contactForm);
      setContactSubmitted(true);
      setContactForm({ name: '', email: '', subject: '', message: '' });
    } catch (err) {
      setContactError('Failed to submit form. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden bg-slate-900 border-slate-700 w-[95vw] md:w-auto mx-2 md:mx-auto">
        <DialogHeader>
          <DialogTitle className="text-lg md:text-xl text-white flex items-center gap-2">
            <HelpCircle className="w-5 h-5 md:w-6 md:h-6 text-blue-400" />
            Help & Support
          </DialogTitle>
          <DialogDescription className="text-gray-400 text-sm">
            Get instant AI help or send us a message
          </DialogDescription>
        </DialogHeader>

        {/* Tab Buttons */}
        <div className="flex gap-2 border-b border-slate-700 pb-2 md:pb-3">
          <Button
            variant={activeTab === 'ai' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setActiveTab('ai')}
            className={`text-xs md:text-sm ${activeTab === 'ai' ? 'bg-blue-600' : 'text-gray-400'}`}
          >
            <Bot className="w-3 h-3 md:w-4 md:h-4 mr-1 md:mr-2" />
            AI Help
          </Button>
          <Button
            variant={activeTab === 'contact' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setActiveTab('contact')}
            className={`text-xs md:text-sm ${activeTab === 'contact' ? 'bg-blue-600' : 'text-gray-400'}`}
          >
            <Mail className="w-3 h-3 md:w-4 md:h-4 mr-1 md:mr-2" />
            Contact
          </Button>
        </div>

        {/* AI Chat Tab */}
        {activeTab === 'ai' && (
          <div className="flex flex-col h-[400px] md:h-[500px]">
            {!isLoggedIn ? (
              <div className="flex-1 flex items-center justify-center">
                <Card className="bg-slate-800/50 border-slate-700 p-6 text-center">
                  <Bot className="w-12 h-12 text-blue-400 mx-auto mb-4" />
                  <p className="text-white mb-2">Please log in to use AI support</p>
                  <p className="text-gray-400 text-sm">
                    Or use the Contact Us form to send a message
                  </p>
                </Card>
              </div>
            ) : (
              <>
                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto space-y-4 p-2">
                  {messages.length === 0 ? (
                    <div className="text-center py-8">
                      <Bot className="w-16 h-16 text-blue-400 mx-auto mb-4 opacity-50" />
                      <p className="text-gray-400 mb-4">
                        Hi! I'm your crypto tax assistant. Ask me anything about:
                      </p>
                      <div className="flex flex-wrap gap-2 justify-center">
                        {suggestedQuestions.slice(0, 4).map((q, idx) => (
                          <Badge
                            key={idx}
                            variant="outline"
                            className="border-slate-600 text-gray-300 cursor-pointer hover:bg-slate-800 px-3 py-1"
                            onClick={() => sendMessage(q)}
                          >
                            {q}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ) : (
                    messages.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        {msg.role === 'assistant' && (
                          <div className="w-8 h-8 rounded-full bg-blue-900 flex items-center justify-center flex-shrink-0">
                            <Bot className="w-5 h-5 text-blue-400" />
                          </div>
                        )}
                        <div
                          className={`max-w-[80%] rounded-lg px-4 py-2 ${
                            msg.role === 'user'
                              ? 'bg-blue-600 text-white'
                              : 'bg-slate-800 text-gray-200'
                          }`}
                        >
                          <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                        </div>
                        {msg.role === 'user' && (
                          <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center flex-shrink-0">
                            <User className="w-5 h-5 text-gray-400" />
                          </div>
                        )}
                      </div>
                    ))
                  )}
                  {loading && (
                    <div className="flex gap-3">
                      <div className="w-8 h-8 rounded-full bg-blue-900 flex items-center justify-center">
                        <Bot className="w-5 h-5 text-blue-400" />
                      </div>
                      <div className="bg-slate-800 rounded-lg px-4 py-2">
                        <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="border-t border-slate-700 pt-3 mt-2">
                  <div className="flex gap-2">
                    <Input
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder="Ask a question..."
                      className="flex-1 bg-slate-800 border-slate-600 text-white"
                      disabled={loading}
                    />
                    <Button
                      onClick={() => sendMessage()}
                      disabled={!inputMessage.trim() || loading}
                      className="bg-blue-600 hover:bg-blue-700"
                    >
                      <Send className="w-4 h-4" />
                    </Button>
                  </div>
                  <p className="text-xs text-gray-500 mt-2 text-center">
                    AI responses are for informational purposes. Consult a tax professional for advice.
                  </p>
                </div>
              </>
            )}
          </div>
        )}

        {/* Contact Form Tab */}
        {activeTab === 'contact' && (
          <div className="space-y-4 py-2">
            {contactSubmitted ? (
              <div className="text-center py-8">
                <CheckCircle2 className="w-16 h-16 text-green-400 mx-auto mb-4" />
                <h3 className="text-xl text-white mb-2">Message Sent!</h3>
                <p className="text-gray-400 mb-4">
                  Thank you for reaching out. We'll get back to you within 24-48 hours.
                </p>
                <Button
                  variant="outline"
                  onClick={() => setContactSubmitted(false)}
                  className="border-slate-600 text-gray-300"
                >
                  Send Another Message
                </Button>
              </div>
            ) : (
              <>
                {contactError && (
                  <Alert className="bg-red-900/20 border-red-700">
                    <AlertDescription className="text-red-300">{contactError}</AlertDescription>
                  </Alert>
                )}
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-4">
                  <div>
                    <label className="text-xs md:text-sm text-gray-400 block mb-1 md:mb-2">Name *</label>
                    <Input
                      value={contactForm.name}
                      onChange={(e) => setContactForm({...contactForm, name: e.target.value})}
                      className="bg-slate-800 border-slate-600 text-white text-sm"
                      placeholder="Your name"
                    />
                  </div>
                  <div>
                    <label className="text-xs md:text-sm text-gray-400 block mb-1 md:mb-2">Email *</label>
                    <Input
                      type="email"
                      value={contactForm.email}
                      onChange={(e) => setContactForm({...contactForm, email: e.target.value})}
                      className="bg-slate-800 border-slate-600 text-white text-sm"
                      placeholder="your@email.com"
                    />
                  </div>
                </div>
                
                <div>
                  <label className="text-sm text-gray-400 block mb-2">Subject</label>
                  <Input
                    value={contactForm.subject}
                    onChange={(e) => setContactForm({...contactForm, subject: e.target.value})}
                    className="bg-slate-800 border-slate-600 text-white"
                    placeholder="What's this about?"
                  />
                </div>
                
                <div>
                  <label className="text-sm text-gray-400 block mb-2">Message *</label>
                  <Textarea
                    value={contactForm.message}
                    onChange={(e) => setContactForm({...contactForm, message: e.target.value})}
                    className="bg-slate-800 border-slate-600 text-white min-h-[150px]"
                    placeholder="How can we help you?"
                  />
                </div>
                
                <Button
                  onClick={submitContactForm}
                  disabled={loading}
                  className="w-full bg-blue-600 hover:bg-blue-700"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4 mr-2" />
                      Send Message
                    </>
                  )}
                </Button>
                
                <p className="text-xs text-gray-500 text-center">
                  You can also email us directly at{' '}
                  <a href="mailto:support@cryptobagtracker.io" className="text-blue-400 hover:underline">
                    support@cryptobagtracker.io
                  </a>
                </p>
              </>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default SupportModal;
