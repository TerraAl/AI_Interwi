import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mail, User, Phone, MapPin, Briefcase } from "lucide-react";

type UserData = {
  name: string;
  email: string;
  phone: string;
  location: string;
  position: string;
  stack: string;
};

export default function Login() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<UserData>({
    name: "",
    email: "",
    phone: "",
    location: "",
    position: "",
    stack: "python",
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name || !formData.email || !formData.phone) {
      alert("Пожалуйста, заполните все обязательные поля");
      return;
    }

    setLoading(true);
    try {
      // Save user data to localStorage for interview
      localStorage.setItem("userData", JSON.stringify(formData));
      
      // Navigate to interview with user data
      navigate("/interview", { state: { userData: formData } });
    } catch (error) {
      console.error("Error:", error);
      alert("Ошибка при входе");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo/Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-gradient-to-r from-indigo-500 to-cyan-400 rounded-full mb-4">
            <Briefcase className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">HireCode AI</h1>
          <p className="text-white/60">Техническое интервью с искусственным интеллектом</p>
        </div>

        {/* Form Card */}
        <div className="bg-slate-800/50 backdrop-blur border border-white/10 rounded-2xl p-8 shadow-2xl">
          <h2 className="text-xl font-semibold text-white mb-6">Заполните контактные данные</h2>
          
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Name */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                <User className="inline w-4 h-4 mr-2" />
                ФИ (обязательно)
              </label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleChange}
                placeholder="Иван Петров"
                className="w-full px-4 py-3 bg-slate-700/50 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
                required
              />
            </div>

            {/* Email */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                <Mail className="inline w-4 h-4 mr-2" />
                Email (обязательно)
              </label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="ivan@example.com"
                className="w-full px-4 py-3 bg-slate-700/50 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
                required
              />
            </div>

            {/* Phone */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                <Phone className="inline w-4 h-4 mr-2" />
                Телефон (обязательно)
              </label>
              <input
                type="tel"
                name="phone"
                value={formData.phone}
                onChange={handleChange}
                placeholder="+7 (999) 123-45-67"
                className="w-full px-4 py-3 bg-slate-700/50 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
                required
              />
            </div>

            {/* Location */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                <MapPin className="inline w-4 h-4 mr-2" />
                Город/Регион
              </label>
              <input
                type="text"
                name="location"
                value={formData.location}
                onChange={handleChange}
                placeholder="Москва"
                className="w-full px-4 py-3 bg-slate-700/50 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
              />
            </div>

            {/* Position */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                <Briefcase className="inline w-4 h-4 mr-2" />
                Должность/Специализация
              </label>
              <input
                type="text"
                name="position"
                value={formData.position}
                onChange={handleChange}
                placeholder="Senior Python Developer"
                className="w-full px-4 py-3 bg-slate-700/50 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
              />
            </div>

            {/* Stack */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                Язык программирования
              </label>
              <select
                name="stack"
                value={formData.stack}
                onChange={handleChange}
                className="w-full px-4 py-3 bg-slate-700/50 border border-white/10 rounded-lg text-white focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
              >
                <option value="python">Python</option>
                <option value="javascript">JavaScript</option>
                <option value="java">Java</option>
                <option value="cpp">C++</option>
              </select>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full mt-8 px-6 py-3 rounded-lg bg-gradient-to-r from-indigo-500 to-cyan-400 text-black font-semibold hover:shadow-lg hover:shadow-indigo-500/50 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                  Загрузка...
                </>
              ) : (
                <>
                  Начать интервью →
                </>
              )}
            </button>
          </form>

          {/* Help text */}
          <p className="text-center text-white/50 text-xs mt-6">
            Ваши данные используются только для отчета об интервью
          </p>
        </div>

        {/* Admin Link */}
        <div className="text-center mt-6">
          <a
            href="/admin"
            className="text-indigo-400 hover:text-indigo-300 text-sm transition"
          >
            Админ панель
          </a>
        </div>
      </div>
    </div>
  );
}
