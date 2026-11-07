import React, { useEffect, useState } from 'react';
import { Bell, Pin } from 'lucide-react';
import { api } from '../services/api';
import { Announcement } from '../types';

export const Announcements: React.FC = () => {
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getAnnouncements().then(setAnnouncements).finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Universitet E'lonlari</h2>
        <p className="text-xs text-slate-500">Muhim bildirishnomalar va dars o'zgarishlari</p>
      </div>

      <div className="space-y-3 pt-2">
        {loading ? (
          <div className="text-center py-8 text-xs text-slate-400">E'lonlar yuklanmoqda...</div>
        ) : announcements.length > 0 ? (
          announcements.map((ann) => (
            <div
              key={ann.id}
              className={`p-5 rounded-2xl border transition ${
                ann.is_pinned
                  ? 'bg-amber-50/70 dark:bg-amber-950/20 border-amber-200 dark:border-amber-900/40 shadow-sm'
                  : 'bg-white dark:bg-slate-800 border-slate-100 dark:border-slate-700 shadow-sm'
              }`}
            >
              <div className="flex justify-between items-start mb-2">
                <h4 className="font-bold text-base text-slate-900 dark:text-white flex items-center gap-1.5">
                  {ann.is_pinned && <Pin className="w-4 h-4 text-amber-500 fill-amber-500" />}
                  <span>{ann.title}</span>
                </h4>
                <span className="text-[10px] text-slate-400">
                  {new Date(ann.created_at).toLocaleDateString('uz-UZ')}
                </span>
              </div>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed whitespace-pre-line">
                {ann.content}
              </p>
            </div>
          ))
        ) : (
          <div className="bg-white dark:bg-slate-800 p-8 rounded-3xl text-center border border-dashed border-slate-200 dark:border-slate-700">
            <Bell className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">Yangi e'lonlar yo'q</p>
            <p className="text-xs text-slate-400 mt-1">Muhim xabarlar bu yerda e'lon qilinadi.</p>
          </div>
        )}
      </div>
    </div>
  );
};
