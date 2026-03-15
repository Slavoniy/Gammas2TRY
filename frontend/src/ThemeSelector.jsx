import React, { useState, useRef, useEffect } from 'react';

const S3_BASE_URL = import.meta.env.VITE_S3_THEMES_BASE_URL || 'https://s3.timeweb.cloud/my-temp-bucket/themes/';

const ImageWithFallback = ({ src, alt, className }) => {
  const [imgError, setImgError] = useState(false);

  // Reset error state when src changes
  useEffect(() => {
    setImgError(false);
  }, [src]);

  if (imgError) {
    return (
      <div className={`bg-gray-200 flex items-center justify-center text-center overflow-hidden ${className}`}>
        <span className="text-sm font-medium text-gray-500 leading-tight px-4 line-clamp-3">{alt}</span>
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      className={`object-cover ${className}`}
      onError={() => setImgError(true)}
    />
  );
};

function ThemeSelector({ themes, selectedThemeId, onSelectTheme, loading }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (loading) {
    return (
      <div className="mt-1 block w-full rounded-md border-gray-300 shadow-sm sm:text-sm p-2 border bg-gray-50 text-gray-500 cursor-wait">
        Загрузка тем...
      </div>
    );
  }

  if (!themes || themes.length === 0) {
    return (
      <div className="mt-1 block w-full rounded-md border-gray-300 shadow-sm sm:text-sm p-2 border bg-gray-50 text-gray-500">
        Темы не найдены
      </div>
    );
  }

  const selectedTheme = themes.find(t => t.id === selectedThemeId) || themes[0];
  const customThemes = themes.filter(t => t.type === 'custom');
  const standardThemes = themes.filter(t => t.type === 'standard' || !t.type);

  const renderDropdownItem = (theme) => {
    const isSelected = selectedThemeId === theme.id;
    const imageUrl = `${S3_BASE_URL}${theme.id}.jpg`;

    return (
      <li
        key={theme.id}
        onClick={() => {
          onSelectTheme(theme.id);
          setIsOpen(false);
        }}
        className={`cursor-pointer flex flex-col items-center p-4 hover:bg-indigo-50 transition-colors border-b border-gray-100 last:border-b-0 ${isSelected ? 'bg-indigo-100 text-indigo-900' : 'text-gray-700'}`}
      >
        <ImageWithFallback src={imageUrl} alt={theme.name || theme.id} className="w-[300px] h-[300px] rounded shadow-md border border-gray-200 mb-3" />
        <div className="flex items-center justify-between w-[300px]">
          <span className="font-medium text-lg truncate pr-2">{theme.name || theme.id}</span>
          {isSelected && (
            <svg className="h-6 w-6 text-indigo-600 shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          )}
        </div>
      </li>
    );
  };

  return (
    <div className="relative mt-1" ref={dropdownRef}>
      {/* Dropdown Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="relative w-full bg-white border border-gray-300 rounded-md shadow-sm pl-3 pr-10 py-2 text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm transition-colors hover:border-indigo-300 min-h-[44px]"
      >
        <span className="flex items-center">
          {selectedTheme ? (
            <>
              <ImageWithFallback src={`${S3_BASE_URL}${selectedTheme.id}.jpg`} alt={selectedTheme.name || selectedTheme.id} className="w-10 h-6 rounded shrink-0 shadow-sm border border-gray-200 mr-3" />
              <span className="block truncate font-medium text-gray-900">{selectedTheme.name || selectedTheme.id}</span>
            </>
          ) : (
            <span className="text-gray-500">Выберите тему</span>
          )}
        </span>
        <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
          <svg className={`h-5 w-5 text-gray-400 transition-transform duration-200 ${isOpen ? 'transform rotate-180' : ''}`} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </span>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute z-50 mt-1 w-[350px] sm:w-full bg-white shadow-2xl rounded-md py-2 text-base ring-1 ring-black ring-opacity-10 max-h-[70vh] overflow-y-auto focus:outline-none sm:text-sm left-1/2 -translate-x-1/2 sm:left-auto sm:translate-x-0">
          <ul role="listbox">
            {customThemes.length > 0 && (
              <>
                <li className="px-4 py-2 text-sm font-bold text-gray-500 uppercase tracking-wider bg-gray-100 sticky top-0 z-10 shadow-sm">Ваши темы (Custom)</li>
                {customThemes.map(renderDropdownItem)}
              </>
            )}

            {standardThemes.length > 0 && (
              <>
                <li className="px-4 py-2 text-sm font-bold text-gray-500 uppercase tracking-wider bg-gray-100 sticky top-0 z-10 shadow-sm">Стандартные темы (Standard)</li>
                {standardThemes.map(renderDropdownItem)}
              </>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

export default ThemeSelector;
