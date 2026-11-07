import React, { useEffect, useState } from 'react';
import { Check, Plus, Trash2, Calendar, AlertCircle } from 'lucide-react';
import { api } from '../services/api';
import { tg } from '../services/telegram';
import { PersonalTask } from '../types';

export const Tasks: React.FC = () => {
  const [tasks, setTasks] = useState<PersonalTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);

  // New task form state
  const [title, setTitle] = useState('');
  const [priority, setPriority] = useState<'LOW' | 'MEDIUM' | 'HIGH'>('MEDIUM');

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const data = await api.getTasks();
      setTasks(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, []);

  const handleToggleComplete = async (task: PersonalTask) => {
    tg.haptic('medium');
    const updated = await api.updateTask(task.id, { is_completed: !task.is_completed });
    setTasks(tasks.map((t) => (t.id === task.id ? updated : t)));
  };

  const handleDelete = async (id: number) => {
    tg.haptic('heavy');
    await api.deleteTask(id);
    setTasks(tasks.filter((t) => t.id !== id));
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    tg.haptic('light');
    const created = await api.createTask({
      title: title.trim(),
      priority,
    });
    setTasks([created, ...tasks]);
    setTitle('');
    setShowAddModal(false);
  };

  const pendingTasks = tasks.filter((t) => !t.is_completed);
  const completedTasks = tasks.filter((t) => t.is_completed);

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">Vazifalarim</h2>
          <p className="text-xs text-slate-500">Shaxsiy topshiriqlar va rejalar</p>
        </div>
        <button
          onClick={() => {
            tg.haptic('light');
            setShowAddModal(true);
          }}
          className="flex items-center space-x-1.5 bg-blue-600 hover:bg-blue-700 text-white px-3.5 py-2 rounded-xl text-xs font-bold shadow-md shadow-blue-500/20"
        >
          <Plus className="w-4 h-4" />
          <span>Yangi vazifa</span>
        </button>
      </div>

      {/* Faol vazifalar */}
      <div className="space-y-2">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
          Bajarilishi kerak ({pendingTasks.length})
        </h3>

        {loading ? (
          <div className="p-4 text-center text-xs text-slate-400">Yuklanmoqda...</div>
        ) : pendingTasks.length > 0 ? (
          pendingTasks.map((t) => (
            <div
              key={t.id}
              className="bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-100 dark:border-slate-700 flex items-center justify-between shadow-sm"
            >
              <div
                className="flex items-center space-x-3 flex-1 cursor-pointer"
                onClick={() => handleToggleComplete(t)}
              >
                <div className="w-6 h-6 rounded-full border-2 border-slate-300 dark:border-slate-600 flex items-center justify-center hover:border-blue-500" />
                <div>
                  <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-100">{t.title}</h4>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full inline-block mt-1 ${
                    t.priority === 'HIGH' ? 'bg-red-50 text-red-600 dark:bg-red-950/40' : 'bg-slate-100 text-slate-600 dark:bg-slate-700'
                  }`}>
                    {t.priority}
                  </span>
                </div>
              </div>

              <button
                onClick={() => handleDelete(t.id)}
                className="text-slate-300 hover:text-red-500 p-2"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))
        ) : (
          <div className="bg-white dark:bg-slate-800 p-6 rounded-2xl text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-700">
            Hozirda faol vazifalar mavjud emas. Yangi vazifa qo'shishingiz mumkin!
          </div>
        )}
      </div>

      {/* Bajarilgan vazifalar */}
      {completedTasks.length > 0 && (
        <div className="space-y-2 pt-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Bajarilgan ({completedTasks.length})
          </h3>
          {completedTasks.map((t) => (
            <div
              key={t.id}
              className="bg-white/60 dark:bg-slate-800/60 p-3.5 rounded-2xl border border-slate-100 dark:border-slate-700/60 flex items-center justify-between opacity-70"
            >
              <div
                className="flex items-center space-x-3 flex-1 cursor-pointer"
                onClick={() => handleToggleComplete(t)}
              >
                <div className="w-6 h-6 rounded-full bg-emerald-500 text-white flex items-center justify-center">
                  <Check className="w-3.5 h-3.5 stroke-[3]" />
                </div>
                <h4 className="text-sm line-through text-slate-500">{t.title}</h4>
              </div>

              <button
                onClick={() => handleDelete(t.id)}
                className="text-slate-300 hover:text-red-500 p-1"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Yangi vazifa modali */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-end sm:items-center justify-center p-4">
          <form
            onSubmit={handleCreateTask}
            className="bg-white dark:bg-slate-800 w-full max-w-sm rounded-3xl p-6 shadow-2xl space-y-4 animate-in fade-in slide-in-from-bottom"
          >
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">Yangi vazifa yaratish</h3>

            <div>
              <label className="text-xs text-slate-500 font-medium block mb-1">Vazifa nomi</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Masalan: Fizika amaliyotini topshirish"
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
                required
              />
            </div>

            <div>
              <label className="text-xs text-slate-500 font-medium block mb-1">Muhimlik darajasi</label>
              <div className="grid grid-cols-3 gap-2">
                {(['LOW', 'MEDIUM', 'HIGH'] as const).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPriority(p)}
                    className={`py-2 text-xs font-bold rounded-xl border transition ${
                      priority === p
                        ? 'border-blue-600 bg-blue-50 dark:bg-blue-950/40 text-blue-600'
                        : 'border-slate-200 dark:border-slate-700 text-slate-500'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-slate-500 bg-slate-100 dark:bg-slate-700"
              >
                Bekor qilish
              </button>
              <button
                type="submit"
                className="flex-1 py-2.5 rounded-xl text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 shadow-md shadow-blue-500/20"
              >
                Qo'shish
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
