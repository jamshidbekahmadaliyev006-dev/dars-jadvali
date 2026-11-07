import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Bell, Calendar as CalendarIcon, CheckCircle2, Clock, MapPin, Sparkles, UploadCloud } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { tg } from '../services/telegram';
import { Announcement, PersonalTask, Schedule } from '../types';
import { LessonSkeleton } from '../components/Skeleton';

export const Home: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [tasks, setTasks] = useState<PersonalTask[]>([]);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(true);

  const dayNames = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY'];
  const todayEnum = dayNames[new Date().getDay()];

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [schedRes, taskRes, annRes] = await Promise.allSettled([
        api.getSchedules(user?.group_id, todayEnum),
        api.getTasks(false),
        api.getAnnouncements(),
      ]);

      if (schedRes.status === 'fulfilled') setSchedules(schedRes.value);
      if (taskRes.status === 'fulfilled') setTasks(taskRes.value.slice(0, 3));
      if (annRes.status === 'fulfilled') setAnnouncements(annRes.value.slice(0, 2));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, [user]);

  // Keyingi darsni topish
  const nextLesson = schedules.length > 0 ? schedules[0] : null;

  return (
    <div className="space-y-6">
      {/* 1. Salomlashish */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-3xl p-6 text-white shadow-xl shadow-blue-500/15 relative overflow-hidden">
        <div className="absolute right-0 top-0 translate-x-4 -translate-y-4 w-32 h-32 bg-white/10 rounded-full blur-2xl" />
        <span className="text-xs font-semibold bg-white/20 px-3 py-1 rounded-full uppercase tracking-wider">
          UniNotify Platform
        </span>
        <h2 className="text-2xl font-bold mt-2">
          Salom, {user?.first_name || 'Talaba'}! 👋
        </h2>
        <p className="text-blue-100 text-sm mt-1">
          {schedules.length > 0
            ? `Bugun sizda ${schedules.length} ta dars rejalashtirilgan.`
            : 'Bugun sizda darslar yo‘q yoki dam olish kuni.'}
        </p>

        {/* Tezkor AI savoli */}
        <button
          onClick={() => {
            tg.haptic('light');
            navigate('/ai-assistant');
          }}
          className="mt-4 flex items-center space-x-2 bg-white/20 hover:bg-white/30 backdrop-blur-md px-4 py-2 rounded-xl text-xs font-medium transition"
        >
          <Sparkles className="w-4 h-4 text-amber-300" />
          <span>AI Yordamchidan so'rash</span>
        </button>
      </div>

      {/* 2. Keyingi dars (Next Lesson Card) */}
      <div>
        <div className="flex justify-between items-center mb-3">
          <h3 className="font-bold text-slate-800 dark:text-slate-100">Keyingi dars</h3>
          <span className="text-xs font-medium text-blue-600 dark:text-blue-400">Bugun</span>
        </div>

        {loading ? (
          <LessonSkeleton />
        ) : nextLesson ? (
          <div className="bg-white dark:bg-slate-800 p-5 rounded-3xl border border-slate-100 dark:border-slate-700 shadow-sm hover:shadow-md transition">
            <div className="flex justify-between items-start">
              <span className="text-xs font-bold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-3 py-1 rounded-full">
                {nextLesson.lesson_type}
              </span>
              <div className="flex items-center text-xs text-slate-500 space-x-1">
                <Clock className="w-3.5 h-3.5" />
                <span>{nextLesson.start_time} - {nextLesson.end_time}</span>
              </div>
            </div>

            <h4 className="text-lg font-bold text-slate-900 dark:text-white mt-3">
              {nextLesson.subject?.name || 'Fan nomi'}
            </h4>

            <div className="flex items-center text-xs text-slate-600 dark:text-slate-300 mt-2 space-x-4">
              <div className="flex items-center space-x-1">
                <MapPin className="w-3.5 h-3.5 text-slate-400" />
                <span>{nextLesson.room?.number || '305'}-auditoriya</span>
              </div>
              <span>•</span>
              <span className="truncate">{nextLesson.teacher?.full_name || "O'qituvchi"}</span>
            </div>
          </div>
        ) : (
          <div className="bg-white dark:bg-slate-800 p-6 rounded-3xl border border-dashed border-slate-200 dark:border-slate-700 text-center">
            <CalendarIcon className="w-8 h-8 text-slate-400 mx-auto mb-2" />
            <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
              Bugun boshqa darslar qolmadi
            </p>
            <p className="text-xs text-slate-400 mt-1">Ertangi darslar jadvalini ko'rishingiz mumkin</p>
          </div>
        )}
      </div>

      {/* 3. Bugungi darslar ro'yxati */}
      {schedules.length > 1 && (
        <div>
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-bold text-slate-800 dark:text-slate-100">Bugungi barcha darslar</h3>
            <button
              onClick={() => navigate('/schedule')}
              className="text-xs text-blue-600 dark:text-blue-400 flex items-center font-medium"
            >
              To'liq jadval <ArrowRight className="w-3 h-3 ml-1" />
            </button>
          </div>
          <div className="space-y-2">
            {schedules.slice(1).map((item) => (
              <div
                key={item.id}
                className="bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-100 dark:border-slate-700 flex justify-between items-center"
              >
                <div>
                  <h5 className="font-semibold text-sm text-slate-800 dark:text-slate-100">
                    {item.subject?.name || 'Fan'}
                  </h5>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {item.room?.number ? `${item.room.number}-xona` : ''} {item.teacher?.full_name ? `• ${item.teacher.full_name}` : ''}
                  </p>
                </div>
                <span className="text-xs font-bold text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-700 px-2.5 py-1 rounded-lg">
                  {item.start_time}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Bugungi vazifalar */}
      <div>
        <div className="flex justify-between items-center mb-3">
          <h3 className="font-bold text-slate-800 dark:text-slate-100">Vazifalarim ({tasks.length})</h3>
          <button
            onClick={() => navigate('/tasks')}
            className="text-xs text-blue-600 dark:text-blue-400 font-medium"
          >
            Barchasi
          </button>
        </div>

        {tasks.length > 0 ? (
          <div className="space-y-2">
            {tasks.map((task) => (
              <div
                key={task.id}
                onClick={async () => {
                  tg.haptic('light');
                  await api.updateTask(task.id, { is_completed: true });
                  loadDashboardData();
                }}
                className="bg-white dark:bg-slate-800 p-3.5 rounded-2xl border border-slate-100 dark:border-slate-700 flex items-center justify-between cursor-pointer hover:border-blue-400 transition"
              >
                <div className="flex items-center space-x-3">
                  <div className="w-5 h-5 rounded-full border-2 border-slate-300 dark:border-slate-600 flex items-center justify-center" />
                  <span className="text-sm font-medium text-slate-800 dark:text-slate-200">
                    {task.title}
                  </span>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                  task.priority === 'HIGH' ? 'bg-red-50 text-red-600 dark:bg-red-950/40' : 'bg-slate-100 text-slate-600 dark:bg-slate-700'
                }`}>
                  {task.priority}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-white dark:bg-slate-800 p-4 rounded-2xl text-center text-xs text-slate-500">
            Barcha vazifalar bajarilgan 🎉
          </div>
        )}
      </div>

      {/* 5. Universitet e'lonlari */}
      {announcements.length > 0 && (
        <div>
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-bold text-slate-800 dark:text-slate-100 flex items-center space-x-1.5">
              <Bell className="w-4 h-4 text-amber-500" />
              <span>Universitet e'lonlari</span>
            </h3>
            <button
              onClick={() => navigate('/announcements')}
              className="text-xs text-blue-600 dark:text-blue-400 font-medium"
            >
              Barchasi
            </button>
          </div>

          <div className="space-y-2">
            {announcements.map((ann) => (
              <div
                key={ann.id}
                className="bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200/60 dark:border-amber-900/40 p-4 rounded-2xl"
              >
                <h5 className="font-bold text-sm text-amber-900 dark:text-amber-200">{ann.title}</h5>
                <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 line-clamp-2">
                  {ann.content}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
