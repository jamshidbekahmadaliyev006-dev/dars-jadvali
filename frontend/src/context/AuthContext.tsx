import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../services/api';
import { tg } from '../services/telegram';
import { User } from '../types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  refreshUser: () => Promise<void>;
  updateUserGroup: (univId: number, facId?: number, grpId?: number) => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  refreshUser: async () => {},
  updateUserGroup: () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const initAuth = async () => {
    try {
      tg.ready();
      tg.expand();

      const initData = tg.initData;
      if (initData) {
        // Haqiqiy Telegram WebApp orqali autentifikatsiya
        const res = await api.authWithTelegram(initData);
        setUser(res.user);
      } else {
        // Brauzer yoki test rejimida
        const token = api.getToken();
        if (token) {
          try {
            const me = await api.getMe();
            setUser(me);
          } catch {
            api.clearToken();
            setDemoUser();
          }
        } else {
          setDemoUser();
        }
      }
    } catch (err) {
      console.error('Auth initialization error:', err);
      setDemoUser();
    } finally {
      setLoading(false);
    }
  };

  const setDemoUser = () => {
    setUser({
      id: 1,
      telegram_id: 12345678,
      first_name: 'Talaba',
      username: 'student_demo',
      role: 'USER',
      language_code: 'uz',
      university_id: 1,
      group_id: 1,
      is_active: true,
    });
  };

  const refreshUser = async () => {
    try {
      const me = await api.getMe();
      setUser(me);
    } catch (e) {
      console.error('Refresh user error:', e);
    }
  };

  const updateUserGroup = (univId: number, facId?: number, grpId?: number) => {
    if (user) {
      setUser({
        ...user,
        university_id: univId,
        faculty_id: facId,
        group_id: grpId,
      });
    }
  };

  useEffect(() => {
    initAuth();
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, refreshUser, updateUserGroup }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
