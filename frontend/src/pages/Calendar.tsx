import React, { useEffect, useState } from 'react';
import { Calendar as CalendarIcon, Clock, Plus, Tag, Trash2 } from 'lucide-react';
import { api } from '../services/api';
import { tg } from '../services/telegram';
import { PersonalEvent } from '../types';

export const Calendar: React.FC = () => {
  const [events, setEvents] = useState<PersonalEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  // Form state
  const [title, setTitle] = useState('');
  const [eventType, setEventType] = useState('exam');
  const [date, setDate] = useState('');

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const data = await api.getEvents();
      setEvents(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !date) return;

    tg.haptic('light');
    const created = await api.createEvent({
      title: title.trim(),
      event_type: eventType,
      start_time: new Date(date).toISOString(),
    });
    setEvents([...events, created]);
    setTitle('');
    setShowModal(false);
  };

  const handleDelete = async (id: number) => {
    tg.haptic('heavy');
    await api.deleteEvent(id);
    setEvents(events.filter((ev) => ev.id !== id));
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">Shaxsiy Kalendar</h2>
          <p className="text-xs text-slate-500">Imtihonlar, deadlinelar va muhim tadbirlar</p>
        </div>
        <button
          onClick={() => {
            tg.haptic('light');
            setShowModal(true);
          }}
          className="flex items-center space-x-1 bg-blue-600 text-white px-3.5 py-2 rounded-xl text-xs font-bold shadow-md shadow-blue-500/20"
        >
          <Plus className="w-4 h-4" />
          <span>Tadbir</span>
        </button>
      </div>

      <div className="space-y-3 pt-2">
        {loading ? (
          <div className="text-center py-8 text-xs text-slate-400">Tadbirlar yuklanmoqda...</div>
        ) : events.length > 0 ? (
          events.map((ev) => {
            const evDate = new Date(ev.start_time);
            return (
              <div
                key={ev.id}
                className="bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-100 dark:border-slate-700 shadow-sm flex items-center justify-between"
              >
                <div className="flex items-start space-x-3.5">
                  <div className="w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 flex flex-col items-center justify-center font-bold">
                    <span className="text-xs uppercase">{evDate.toLocaleDateString('uz-UZ', { month: 'short' })}</span>
                    <span className="text-sm leading-none">{evDate.getDate()}</span>
                  </div>
                  <div>
                    <h4 className="font-bold text-sm text-slate-800 dark:text-slate-100">{ev.title}</h4>
                    <div className="flex items-center space-x-2 text-xs text-slate-400 mt-1">
                      <span className="uppercase text-[10px] font-bold bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded-full text-slate-600 dark:text-slate-300">
                        {ev.event_type}
                      </span>
                      <span>{evDate.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => handleDelete(ev.id)}
                  className="text-slate-300 hover:text-red-500 p-2"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            );
          })
        ) : (
          <div className="bg-white dark:bg-slate-800 p-8 rounded-3xl text-center border border-dashed border-slate-200 dark:border-slate-700">
            <CalendarIcon className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">Kalendaringiz bo'sh</p>
            <p className="text-xs text-slate-400 mt-1">Yaqinlashib kelayotgan imtihon yoki topshiriqlarni qo'shing.</p>
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-end sm:items-center justify-center p-4">
          <form
            onSubmit={handleCreate}
            className="bg-white dark:bg-slate-800 w-full max-w-sm rounded-3xl p-6 shadow-2xl space-y-4"
          >
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">Tadbir qo'shish</h3>
            <div>
              <label className="text-xs text-slate-500 font-medium block mb-1">Nomi</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Oraliq nazorat / Mustaqil ish"
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-sm focus:outline-none"
                required
              />
            </div>

            <div>
              <label className="text-xs text-slate-500 font-medium block mb-1">Turi</label>
              <select
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-sm focus:outline-none"
              >
                <option value="exam">Imtihon (Exam)</option>
                <option value="deadline">Topshiriq muddati (Deadline)</option>
                <option value="homework">Uy vazifasi</option>
                <option value="meeting">Uchrashuv</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-slate-500 font-medium block mb-1">Sana va vaqt</label>
              <input
                type="datetime-local"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-sm focus:outline-none"
                required
              />
            </div>

            <div className="flex space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-slate-500 bg-slate-100 dark:bg-slate-700"
              >
                Bekor qilish
              </button>
              <button
                type="submit"
                className="flex-1 py-2.5 rounded-xl text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 shadow-md shadow-blue-500/20"
              >
                Saqlash
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
