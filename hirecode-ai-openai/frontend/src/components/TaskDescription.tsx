type Props = {
  title: string;
  description: string;
  followUp: string[];
};

export default function TaskDescription({ title, description, followUp }: Props) {
  return (
    <section className="rounded-3xl bg-panel/60 border border-white/5 p-5 space-y-4">
      <header>
        <p className="text-xs uppercase text-white/50">Текущая задача</p>
        <h1 className="text-2xl font-semibold">{title}</h1>
      </header>
      <p className="text-white/70 leading-relaxed">{description}</p>
      <div>
        <p className="text-xs uppercase text-white/40 mb-1">Дополнительные вопросы</p>
        <ul className="space-y-2 text-white/70 text-sm">
          {followUp.map((item) => (
            <li key={item} className="flex gap-2 items-start">
              <span className="text-emerald-300">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

