import React, { useEffect, useState } from 'react';
import { Bell, CheckCircle2, ChevronRight, Globe, Moon, ShieldCheck, Sun, Upload, User as UserIcon } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { tg } from '../services/telegram';
import { Faculty, Group, University } from '../types';

export const Profile: React.FC = () => {
  const { user, updateUserGroup } = useAuth();

  const [universities, setUniversities] = useState<University[]>([]);
  const [faculties, setFaculties] = useState<Faculty[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);

  const [selectedUniv, setSelectedUniv] = useState<number>(user?.university_id || 1);
  const [selectedFac, setSelectedFac] = useState<number | undefined>(user?.faculty_id);
  const [selectedGrp, setSelectedGrp] = useState<number | undefined>(user?.group_id);

  const [reminderEnabled, setReminderEnabled] = useState(true);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    api.getUniversities().then((data) => {
      setUniversities(data);
      if (data.length > 0 && !selectedUniv) {
        setSelectedUniv(data[0].id);
      }
    });
  }, []);

  useEffect(() => {
    if (selectedUniv) {
      api.getFaculties(selectedUniv).then(setFaculties);
      api.getGroups(selectedUniv).then(setGroups);
    }
  }, [selectedUniv]);

  const handleSaveAcademic = () => {
    tg.haptic('medium');
    updateUserGroup(selectedUniv, selectedFac, selectedGrp);
    alert('Universitet va guruh muvaffaqiyatli saqlandi!');
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadSuccess(false);
    tg.haptic('light');

    const formData = new FormData();
    formData.append('university_id', selectedUniv.toString());
    if (selectedFac) formData.append('faculty_id', selectedFac.toString());
    if (selectedGrp) formData.append('group_id', selectedGrp.toString());
    formData.append('file', file);

    try {
      await api.submitScheduleScreenshot(formData);
      setUploadSuccess(true);
      tg.haptic('heavy');
    } catch (err: any) {
      alert(`Xatolik: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Profil bosh kartasi */}
      <div className="bg-white dark:bg-slate-800 p-6 rounded-3xl border border-slate-100 dark:border-slate-700 shadow-sm flex items-center space-x-4">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white text-xl font-bold shadow-md shadow-blue-500/20">
          {user?.first_name ? user.first_name[0] : 'U'}
        </div>
        <div>
          <h3 className="font-bold text-lg text-slate-900 dark:text-white">
            {user?.first_name} {user?.last_name || ''}
          </h3>
          <p className="text-xs text-slate-500">@{user?.username || 'telegram_user'}</p>
          <div className="flex items-center space-x-1.5 mt-1.5">
            <span className="text-[10px] font-bold bg-blue-50 text-blue-600 dark:bg-blue-900/40 dark:text-blue-300 px-2.5 py-0.5 rounded-full">
              Rol: {user?.role || 'USER'}
            </span>
          </div>
        </div>
      </div>

      {/* Universitet va Guruhni biriktirish */}
      <div className="bg-white dark:bg-slate-800 p-5 rounded-3xl border border-slate-100 dark:border-slate-700 shadow-sm space-y-3">
        <h4 className="font-bold text-sm text-slate-900 dark:text-white">O'quv muassasasi ma'lumotlari</h4>

        <div>
          <label className="text-xs text-slate-500 font-medium block mb-1">Universitet</label>
          <select
            value={selectedUniv}
            onChange={(e) => setSelectedUniv(Number(e.target.value))}
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-xs focus:outline-none"
          >
            {universities.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name} ({u.short_name || u.name})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs text-slate-500 font-medium block mb-1">Fakultet</label>
          <select
            value={selectedFac || ''}
            onChange={(e) => setSelectedFac(Number(e.target.value) || undefined)}
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-xs focus:outline-none"
          >
            <option value="">Fakultetni tanlang</option>
            {faculties.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs text-slate-500 font-medium block mb-1">Guruh</label>
          <select
            value={selectedGrp || ''}
            onChange={(e) => setSelectedGrp(Number(e.target.value) || undefined)}
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-xs focus:outline-none"
          >
            <option value="">Guruhni tanlang</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={handleSaveAcademic}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition shadow-sm"
        >
          Ma'lumotlarni saqlash
        </button>
      </div>

      {/* Dars jadvali screenshotini yuklash */}
      <div className="bg-white dark:bg-slate-800 p-5 rounded-3xl border border-slate-100 dark:border-slate-700 shadow-sm space-y-3">
        <h4 className="font-bold text-sm text-slate-900 dark:text-white flex items-center space-x-2">
          <Upload className="w-4 h-4 text-blue-600" />
          <span>Dars jadvali screenshotini yuklash</span>
        </h4>
        <p className="text-xs text-slate-500">
          Jadval rasmini yuklang, Sun'iy intellekt (AI) uni avtomatik tarzda tahlil qiladi.
        </p>

        <label className="border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-2xl p-4 flex flex-col items-center justify-center cursor-pointer hover:border-blue-500 transition">
          <input
            type="file"
            accept="image/*"
            onChange={handleFileUpload}
            disabled={uploading}
            className="hidden"
          />
          <Upload className="w-6 h-6 text-slate-400 mb-1" />
          <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">
            {uploading ? 'AI tahlil qilmoqda...' : 'Screenshot tanlash'}
          </span>
        </label>

        {uploadSuccess && (
          <div className="flex items-center space-x-2 text-xs text-emerald-600 bg-emerald-50 dark:bg-emerald-950/40 p-2.5 rounded-xl">
            <CheckCircle2 className="w-4 h-4" />
            <span>Jadval qabul qilindi va AI tomonidan tahlil qilindi!</span>
          </div>
        )}
      </div>

      {/* Bildirishnomalar va Eslatmalar sozlamalari */}
      <div className="bg-white dark:bg-slate-800 p-5 rounded-3xl border border-slate-100 dark:border-slate-700 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-blue-950 text-blue-600 flex items-center justify-center">
              <Bell className="w-5 h-5" />
            </div>
            <div>
              <h5 className="font-semibold text-sm text-slate-800 dark:text-white">Dars eslatmalari</h5>
              <p className="text-[11px] text-slate-500">Darsdan 15 minut oldin Telegram xabari</p>
            </div>
          </div>
          <input
            type="checkbox"
            checked={reminderEnabled}
            onChange={(e) => {
              tg.haptic('light');
              setReminderEnabled(e.target.checked);
            }}
            className="w-5 h-5 text-blue-600 rounded-lg accent-blue-600 cursor-pointer"
          />
        </div>
      </div>
    </div>
  );
};
