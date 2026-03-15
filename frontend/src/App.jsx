import React, { useState, useEffect } from 'react';
import './App.css';
import ThemeSelector from './ThemeSelector';

function App() {
  const [themes, setThemes] = useState([]);
  const [loadingThemes, setLoadingThemes] = useState(true);

  const [formData, setFormData] = useState({
    formatDimensions: 'presentation|16x9', // format|dimensions
    textMode: 'generate',
    inputText: '',
    numCards: 10,
    additionalInstructions: '',
    amount: 'medium',
    tone: '',
    audience: '',
    language: 'ru',
    themeId: '',
    exportAs: 'pdf'
  });

  const [isGenerating, setIsGenerating] = useState(false);
  const [downloadLink, setDownloadLink] = useState(null);
  const [error, setError] = useState(null);

  const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

  useEffect(() => {
    fetchThemes();
  }, []);

  const fetchThemes = async () => {
    try {
      setLoadingThemes(true);
      const response = await fetch(`${API_BASE_URL}/themes`);
      if (!response.ok) throw new Error('Не удалось загрузить темы');
      const data = await response.json();
      setThemes(data.themes || []);
      if (data.themes && data.themes.length > 0) {
        setFormData(prev => ({ ...prev, themeId: data.themes[0].id }));
      }
    } catch (err) {
      console.error(err);
      setError('Не удалось загрузить темы. Используются значения по умолчанию.');
    } finally {
      setLoadingThemes(false);
    }
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleThemeSelect = (themeId) => {
    setFormData(prev => ({ ...prev, themeId }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsGenerating(true);
    setDownloadLink(null);
    setError(null);

    // Parse combined format/dimensions field
    const [format, dimensions] = formData.formatDimensions.split('|');

    const payload = {
      format,
      dimensions,
      textMode: formData.textMode,
      inputText: formData.inputText,
      numCards: parseInt(formData.numCards),
      additionalInstructions: formData.additionalInstructions,
      amount: formData.amount,
      tone: formData.tone,
      audience: formData.audience,
      language: formData.language,
      themeId: formData.themeId,
      exportAs: formData.exportAs
    };

    try {
      const response = await fetch(`${API_BASE_URL}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Генерация не удалась');
      }

      const data = await response.json();
      const generationId = data.generationId;

      if (!generationId) {
        throw new Error('Сервер не вернул ID генерации');
      }

      // Start polling
      pollGeneration(generationId, formData.exportAs);

    } catch (err) {
      console.error(err);
      setError(err.message || 'Произошла ошибка во время генерации.');
      setIsGenerating(false);
    }
  };

  const pollGeneration = (generationId, exportAs) => {
    const pollInterval = 5000; // 5 seconds
    const maxAttempts = 60; // 5 minutes max
    let attempts = 0;

    const checkStatus = async () => {
      attempts++;
      try {
        const response = await fetch(`${API_BASE_URL}/generation/${generationId}`);
        if (!response.ok) {
           const errorData = await response.json();
           throw new Error(errorData.detail || 'Ошибка при проверке статуса');
        }

        const data = await response.json();

        if (data.status === 'completed') {
          if (data.downloadUrl) {
            setDownloadLink(data.downloadUrl);
          } else {
            setError('Презентация создана, но ссылка на скачивание не найдена в ответе API Gamma.');
          }
          setIsGenerating(false);
          return;
        } else if (data.status === 'failed' || data.status === 'error' || data.status === 'cancelled') {
          throw new Error(`Генерация завершилась со статусом: ${data.status}`);
        }

        if (attempts >= maxAttempts) {
          throw new Error('Превышено время ожидания генерации');
        }

        // Continue polling
        setTimeout(checkStatus, pollInterval);

      } catch (err) {
        console.error(err);
        setError(err.message || 'Ошибка при проверке статуса генерации.');
        setIsGenerating(false);
      }
    };

    // Start first check
    setTimeout(checkStatus, pollInterval);
  };

  return (
    <div className="min-h-screen bg-gray-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto bg-white rounded-xl shadow-md p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-extrabold text-gray-900">ИИ Генератор с Gamma</h1>
          <p className="mt-2 text-sm text-gray-600">Мгновенное создание презентаций и документов</p>
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border-l-4 border-red-400 p-4">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Format & Dimensions */}
            <div>
              <label className="block text-sm font-medium text-gray-700">Формат и пропорции</label>
              <select name="formatDimensions" value={formData.formatDimensions} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border">
                <option value="presentation|16x9">Презентация 16:9</option>
                <option value="presentation|4x3">Презентация 4:3</option>
                <option value="document|a4">Документ A4</option>
                <option value="webpage|a4">Веб-сайт</option>
              </select>
            </div>

            {/* Text Mode */}
            <div>
              <label className="block text-sm font-medium text-gray-700">Текстовый режим</label>
              <select name="textMode" value={formData.textMode} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border">
                <option value="generate">Сгенерировать с нуля</option>
                <option value="condense">Сжать готовый текст</option>
                <option value="preserve">Оставить текст как есть</option>
              </select>
            </div>
          </div>

          {/* Input Text */}
          <div>
            <label className="block text-sm font-medium text-gray-700">Основной промпт / Текст</label>
            <textarea required name="inputText" rows={4} value={formData.inputText} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border" placeholder="Введите ваш промпт или полный текст здесь..."></textarea>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Number of Cards */}
            <div>
              <label className="block text-sm font-medium text-gray-700">Количество слайдов/карточек (1-60)</label>
              <input type="number" name="numCards" min="1" max="60" required value={formData.numCards} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border" />
            </div>

             {/* Language */}
             <div>
              <label className="block text-sm font-medium text-gray-700">Язык генерации</label>
              <select name="language" value={formData.language} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border">
                <option value="ru">Русский (ru)</option>
                <option value="en">Английский (en)</option>
                <option value="es">Испанский (es)</option>
                <option value="fr">Французский (fr)</option>
                <option value="de">Немецкий (de)</option>
              </select>
            </div>
          </div>

          {/* Additional Instructions */}
          <div>
            <label className="block text-sm font-medium text-gray-700">Дополнительные инструкции (макс. 2000 символов)</label>
            <textarea name="additionalInstructions" maxLength={2000} rows={2} value={formData.additionalInstructions} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border" placeholder="Есть какие-то особые пожелания по структуре?"></textarea>
          </div>

          {/* Text Volume Amount */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Объем текста</label>
            <div className="flex space-x-4">
              {[
                { val: 'brief', label: 'Краткий' },
                { val: 'medium', label: 'Средний' },
                { val: 'detailed', label: 'Подробный' },
                { val: 'extensive', label: 'Обширный' }
              ].map(item => (
                <label key={item.val} className="inline-flex items-center">
                  <input type="radio" name="amount" value={item.val} checked={formData.amount === item.val} onChange={handleChange} className="form-radio text-indigo-600" />
                  <span className="ml-2 text-sm text-gray-700">{item.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Tone */}
            <div>
              <label className="block text-sm font-medium text-gray-700">Тон</label>
              <input type="text" name="tone" value={formData.tone} onChange={handleChange} placeholder="например: Профессиональный, Игривый" className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border" />
            </div>

            {/* Audience */}
            <div>
              <label className="block text-sm font-medium text-gray-700">Аудитория</label>
              <input type="text" name="audience" value={formData.audience} onChange={handleChange} placeholder="например: Студенты, Инвесторы" className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border" />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 relative z-10">
            {/* Theme Selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700">Оформление (Тема)</label>
              <ThemeSelector
                themes={themes}
                selectedThemeId={formData.themeId}
                onSelectTheme={handleThemeSelect}
                loading={loadingThemes}
              />
              {/* Скрытый input для нативной валидации формы */}
              <input type="hidden" name="themeId" value={formData.themeId} required />
            </div>

            {/* Export Format */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Формат экспорта</label>
              <div className="flex space-x-4">
                <label className="inline-flex items-center">
                  <input type="radio" name="exportAs" value="pdf" checked={formData.exportAs === 'pdf'} onChange={handleChange} className="form-radio text-indigo-600" />
                  <span className="ml-2 text-sm text-gray-700">PDF</span>
                </label>
                <label className="inline-flex items-center">
                  <input type="radio" name="exportAs" value="pptx" checked={formData.exportAs === 'pptx'} onChange={handleChange} className="form-radio text-indigo-600" />
                  <span className="ml-2 text-sm text-gray-700">PowerPoint (PPTX)</span>
                </label>
              </div>
            </div>
          </div>


          {/* Actions */}
          <div className="pt-4 border-t border-gray-200 mt-8 relative z-0">
            {downloadLink ? (
              <div className="flex flex-col items-center">
                <div className="text-green-600 mb-4 font-medium text-lg">Генерация завершена!</div>
                <a href={downloadLink} target="_blank" rel="noopener noreferrer" className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 transition-colors">
                  Скачать {formData.exportAs.toUpperCase()}
                </a>
                <button type="button" onClick={() => setDownloadLink(null)} className="mt-4 text-sm text-indigo-600 hover:text-indigo-500">
                  Сгенерировать еще
                </button>
              </div>
            ) : (
              <button type="submit" disabled={isGenerating || !formData.themeId} className={`w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white transition-colors ${(isGenerating || !formData.themeId) ? 'bg-indigo-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500'}`}>
                {isGenerating ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Генерация... Это может занять некоторое время
                  </>
                ) : (
                  'Сгенерировать'
                )}
              </button>
            )}
          </div>

        </form>
      </div>
    </div>
  );
}

export default App;
