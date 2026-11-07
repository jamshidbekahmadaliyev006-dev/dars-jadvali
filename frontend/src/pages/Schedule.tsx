import React, { useEffect, useState } from 'react';
import { Clock, MapPin, User as UserIcon, Calendar, Info, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { tg } from '../services/telegram';
import { Schedule as ScheduleType } from '../types';
import { LessonSkeleton } from '../components/Skeleton';

export const Schedule: React.FC = () => {
  const { user } = useAuth();

  const days = [
    { key: 'MONDAY', label: 'Dush' },
    { key: 'TUESDAY', label: 'Sesh' },
    { key: 'WEDNESDAY', label: 'Chor' },
    { key: 'THURSDAY', label: 'Pay' },
    { key: 'FRIDAY', label: 'Juma' },
    { key: 'SATURDAY', label: 'Shan' },
  ];

  const [activeDay, setActiveDay] = useState<string>('MONDAY');
  const [schedules, setSchedules] = useState<ScheduleType[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedLesson, setSelectedLesson] = useState<ScheduleType | null>(null);

  const fetchSchedule = async (day: string) => {
    setLoading(true);
    try {
      const data = await api.getSchedules(user?.group_id, day);
      setSchedules(data);
    } catch (e) {
      console.error(e);
      setSchedules([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Bugungi kunga mos tabni avtomatik tanlash
    const currentDayIdx = new Date().getDay(); // 0 is Sunday
    const mappedDay = days[currentDayIdx - 1]?.key || 'MONDAY';
    setActiveDay(mappedDay);
    fetchSchedule(mappedDay);
  }, [user]);

  const handleTabChange = (dayKey: string) => {
    tg.haptic('light');
    setActiveDay(dayKey);
    fetchSchedule(dayKey);
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Dars Jadvali</h2>
        <span className="text-xs bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 font-semibold px-2.5 py-1 rounded-lg">
          {user?.group_id ? `Guruh #${user.group_id}` : 'Guruh biriktirilmagan'}
        </span>
      </div>

      {/* Kunlar Tab Bar */}
      <div className="flex bg-slate-200/80 dark:bg-slate-800 p-1 rounded-2xl overflow-x-auto no-scrollbar space-x-1">
        {days.map((d) => (
          <button
            key={d.key}
            onClick={() => handleTabChange(d.key)}
            className={`flex-1 min-w-[50px] py-2 text-xs font-bold rounded-xl transition-all duration-200 ${
              activeDay === d.key
                ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-white shadow-sm'
                : 'text-slate-500 hover:text-slate-800 dark:text-slate-400'
            }`}
          >
            {d.label}
          </button>
        ))}
      </div>

      {/* Darslar ro'yxati */}
      <div className="space-y-3 pt-2">
        {loading ? (
          <>
            <LessonSkeleton />
            <LessonSkeleton />
          </>
        ) : schedules.length > 0 ? (
          schedules.map((lesson) => (
            <div
              key={lesson.id}
              onClick={() => {
                tg.haptic('medium');
                setSelectedLesson(lesson);
              }}
              className="bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-100 dark:border-slate-700 shadow-sm hover:shadow-md transition cursor-pointer"
            >
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-bold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 px-2.5 py-0.5 rounded-full">
                  {lesson.lesson_type}
                </span>
                <div className="flex items-center text-xs text-slate-500 space-x-1">
                  <Clock className="w-3.5 h-3.5" />
                  <span className="font-semibold">{lesson.start_time} - {lesson.end_time}</span>
                </div>
              </div>

              <h4 className="font-bold text-base text-slate-900 dark:text-white">
                {lesson.subject?.name || 'Fan nomi'}
              </h4>

              <div className="flex items-center text-xs text-slate-500 dark:text-slate-400 mt-2 space-x-4">
                <div className="flex items-center space-x-1">
                  <MapPin className="w-3.5 h-3.5" />
                  <span>{lesson.room?.number || '305'}-xona</span>
                </div>
                <span>•</span>
                <div className="flex items-center space-x-1 truncate">
                  <UserIcon className="w-3.5 h-3.5" />
                  <span className="truncate">{lesson.teacher?.full_name || "O'qituvchi"}</span>
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="bg-white dark:bg-slate-800 p-8 rounded-3xl text-center border border-dashed border-slate-200 dark:border-slate-700">
            <Calendar className="w-10 h-10 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
            <p className="font-semibold text-slate-700 dark:text-slate-300 text-sm">
              Ushbu kunga darslar belgilanmagan
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Jadval screenshotini yuborib uni avtomatik kiritishingiz mumkin.
            </p>
          </div>
        )}
      </div>

      {/* Dars Tafsilotlari Modali */}
      {selectedLesson && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-end sm:items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-800 w-full max-w-sm rounded-3xl p-6 shadow-2xl space-y-4 animate-in fade-in slide-in-from-bottom duration-200">
            <div className="flex justify-between items-center">
              <span className="text-xs font-bold text-blue-600 bg-blue-50 dark:bg-blue-900/30 px-3 py-1 rounded-full">
                {selectedLesson.lesson_type}
              </span>
              <button
                onClick={() => setSelectedLesson(null)}
                className="p-1 rounded-full text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <h3 className="text-xl font-bold text-slate-900 dark:text-white">
                {selectedLesson.subject?.name}
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                Dars vaqti: {selectedLesson.start_time} - {selectedLesson.end_time}
              </p>
            </div>

            <div className="space-y-2 text-sm text-slate-600 dark:text-slate-300 border-t border-b border-slate-100 dark:border-slate-700 py-3">
              <div className="flex justify-between">
                <span className="text-slate-400">O'qituvchi:</span>
                <span className="font-medium">{selectedLesson.teacher?.full_name || 'Aniqlanmagan'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Auditoriya:</span>
                <span className="font-medium">{selectedLesson.room?.number || 'Aniqlanmagan'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Eslatma:</span>
                <span className="font-medium text-emerald-600">15 daqiqa oldin Telegram</span>
              </div>
            </div>

            <button
              onClick={() => setSelectedLesson(null)}
              className="w-full py-3 bg-blue-600 text-white rounded-xl font-bold text-sm shadow-md shadow-blue-500/20"
            >
              Yopish
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
