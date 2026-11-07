import React from 'react';
import { NavLink } from 'react-router-dom';
import { Calendar, CheckSquare, Home, MessageSquareQuote, Table } from 'lucide-react';
import { tg } from '../services/telegram';

export const BottomNav: React.FC = () => {
  const navItems = [
    { to: '/', icon: Home, label: 'Asosiy' },
    { to: '/schedule', icon: Table, label: 'Jadval' },
    { to: '/tasks', icon: CheckSquare, label: 'Vazifalar' },
    { to: '/calendar', icon: Calendar, label: 'Kalendar' },
    { to: '/ai-assistant', icon: MessageSquareQuote, label: 'AI Yordamchi' },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-30 bg-white/90 dark:bg-slate-900/90 backdrop-blur-lg border-t border-slate-200 dark:border-slate-800 pb-safe">
      <div className="max-w-md mx-auto flex items-center justify-around py-2 px-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => tg.haptic('light')}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center py-1 px-3 rounded-xl transition-all duration-200 ${
                  isActive
                    ? 'text-blue-600 dark:text-blue-400 font-semibold scale-105'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-800'
                }`
              }
            >
              <Icon className="w-5 h-5 mb-1" />
              <span className="text-[10px] tracking-tight">{item.label}</span>
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
};
