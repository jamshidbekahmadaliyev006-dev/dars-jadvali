import React, { useState } from 'react';
import { Bot, Send, Sparkles, User as UserIcon } from 'lucide-react';
import { api } from '../services/api';
import { tg } from '../services/telegram';

interface ChatMessage {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  time: string;
}

export const AIAssistant: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'ai',
      text: "Assalomu alaykum! Men UniNotify AI yordamchisiman. Dars jadvalingiz, yaqinlashayotgan vazifalaringiz yoki kunlik reja bo'yicha savollaringizga bajonidil javob beraman.",
      time: new Date().toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const quickPrompts = [
    'Bugun nechta darsim bor?',
    'Keyingi darsim qachon?',
    'Ertaga qaysi fanlar bor?',
    'Qaysi vazifalarim yaqin?',
    'Bugungi reja tuzib ber',
  ];

  const handleSend = async (textToSend: string) => {
    const q = textToSend.trim();
    if (!q || loading) return;

    tg.haptic('light');

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: q,
      time: new Date().toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await api.askAIAssistant(q);
      const aiMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: res.answer,
        time: new Date().toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, aiMsg]);
      tg.haptic('medium');
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: 'ai',
          text: "Kechirasiz, ma'lumotlarni tahlil qilishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.",
          time: new Date().toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-140px)]">
      {/* Header */}
      <div className="flex items-center space-x-2.5 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-amber-500 to-orange-500 flex items-center justify-center text-white shadow-md shadow-orange-500/20">
          <Sparkles className="w-5 h-5" />
        </div>
        <div>
          <h2 className="font-bold text-slate-900 dark:text-white text-base">AI Talaba Yordamchisi</h2>
          <p className="text-[10px] text-emerald-600 font-semibold flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Faol va tayyor
          </p>
        </div>
      </div>

      {/* Xabarlar maydoni */}
      <div className="flex-1 overflow-y-auto py-4 space-y-3 pr-1">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex items-start space-x-2.5 ${m.sender === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}
          >
            <div
              className={`w-7 h-7 rounded-xl flex items-center justify-center flex-shrink-0 text-white ${
                m.sender === 'user' ? 'bg-blue-600' : 'bg-gradient-to-tr from-amber-500 to-orange-500'
              }`}
            >
              {m.sender === 'user' ? <UserIcon className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>
            <div
              className={`max-w-[80%] p-3.5 rounded-2xl text-xs leading-relaxed whitespace-pre-line shadow-sm ${
                m.sender === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-none'
                  : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 border border-slate-100 dark:border-slate-700 rounded-tl-none'
              }`}
            >
              {m.text}
              <div className={`text-[9px] mt-1 text-right ${m.sender === 'user' ? 'text-blue-200' : 'text-slate-400'}`}>
                {m.time}
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center space-x-2 text-xs text-slate-400 pl-9">
            <span className="w-2 h-2 rounded-full bg-orange-400 animate-bounce" />
            <span className="w-2 h-2 rounded-full bg-orange-400 animate-bounce [animation-delay:0.2s]" />
            <span className="w-2 h-2 rounded-full bg-orange-400 animate-bounce [animation-delay:0.4s]" />
            <span className="text-[11px] ml-1">AI tahlil qilmoqda...</span>
          </div>
        )}
      </div>

      {/* Tezkor Savollar Chips */}
      <div className="py-2 overflow-x-auto no-scrollbar flex space-x-1.5 flex-shrink-0">
        {quickPrompts.map((prompt) => (
          <button
            key={prompt}
            onClick={() => handleSend(prompt)}
            className="text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-3 py-1.5 rounded-xl whitespace-nowrap hover:bg-blue-50 hover:text-blue-600 transition"
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* Input bar */}
      <div className="pt-2 flex items-center space-x-2 flex-shrink-0">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend(input)}
          placeholder="Savolingizni yozing..."
          className="flex-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl px-4 py-2.5 text-xs text-slate-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={() => handleSend(input)}
          disabled={!input.trim() || loading}
          className="w-10 h-10 rounded-2xl bg-blue-600 disabled:opacity-50 text-white flex items-center justify-center shadow-md shadow-blue-500/20"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
