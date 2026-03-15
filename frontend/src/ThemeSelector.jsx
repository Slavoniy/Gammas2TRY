import React, { useState } from 'react';

const S3_BASE_URL = import.meta.env.VITE_S3_THEMES_BASE_URL || 'https://s3.timeweb.cloud/my-temp-bucket/themes/';

// Вынесли ImageWithFallback наружу, чтобы избежать пересоздания компонента при каждом рендере ThemeSelector
const ImageWithFallback = ({ src, alt }) => {
  const [imgError, setImgError] = useState(false);

  if (imgError) {
    return (
      <div className="w-full h-24 bg-gray-200 flex items-center justify-center rounded-t-md p-2 text-center">
        <span className="text-sm font-medium text-gray-600 line-clamp-2">{alt}</span>
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      className="w-full h-24 object-cover rounded-t-md"
      onError={() => setImgError(true)}
    />
  );
};

function ThemeSelector({ themes, selectedThemeId, onSelectTheme, loading }) {
  if (loading) {
    return (
      <div className="mt-1 flex justify-center items-center h-32 bg-gray-50 rounded-md border border-gray-200">
        <span className="text-gray-500">Загрузка тем...</span>
      </div>
    );
  }

  if (!themes || themes.length === 0) {
    return (
      <div className="mt-1 flex justify-center items-center h-32 bg-gray-50 rounded-md border border-gray-200">
        <span className="text-gray-500">Темы не найдены</span>
      </div>
    );
  }

  const renderThemeCard = (theme) => {
    const isSelected = selectedThemeId === theme.id;
    const imageUrl = `${S3_BASE_URL}${theme.id}.jpg`;

    return (
      <div
        key={theme.id}
        onClick={() => onSelectTheme(theme.id)}
        className={`cursor-pointer rounded-md border-2 transition-all duration-200 flex flex-col ${
          isSelected
            ? 'border-indigo-600 ring-2 ring-indigo-200 shadow-md transform scale-[1.02]'
            : 'border-gray-200 hover:border-indigo-300 hover:shadow-sm'
        }`}
      >
        <ImageWithFallback src={imageUrl} alt={theme.name || theme.id} />
        <div className={`p-2 text-center border-t ${isSelected ? 'bg-indigo-50 border-indigo-200' : 'bg-white border-gray-200'} rounded-b-md`}>
          <p className={`text-xs font-medium truncate ${isSelected ? 'text-indigo-700' : 'text-gray-700'}`}>
            {theme.name || theme.id}
          </p>
        </div>
      </div>
    );
  };

  const customThemes = themes.filter(t => t.type === 'custom');
  const standardThemes = themes.filter(t => t.type === 'standard' || !t.type);

  return (
    <div className="space-y-6 mt-1">
      {customThemes.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-500 mb-3">Ваши темы (Custom)</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {customThemes.map(renderThemeCard)}
          </div>
        </div>
      )}

      {standardThemes.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-500 mb-3">Стандартные темы (Standard)</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {standardThemes.map(renderThemeCard)}
          </div>
        </div>
      )}
    </div>
  );
}

export default ThemeSelector;
