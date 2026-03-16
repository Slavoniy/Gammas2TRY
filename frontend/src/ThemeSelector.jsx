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
      className={`${className}`}
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

  const renderDropdownItem = (theme) => {
    const isSelected = selectedThemeId === theme.id;
    const imageUrl = `${S3_BASE_URL}${theme.id}.png`;

    return (
      <li
        key={theme.id}
        onClick={() => {
          onSelectTheme(theme.id);
          setIsOpen(false);
        }}
        className={`cursor-pointer flex flex-col items-center overflow-hidden hover:bg-indigo-50 transition-colors border-b border-gray-100 last:border-b-0 ${isSelected ? 'bg-indigo-100 text-indigo-900' : 'text-gray-700'}`}
      >
        <ImageWithFallback src={imageUrl} alt={theme.name || theme.id} className="w-full aspect-video object-cover shrink-0" />
        <div className="flex items-center justify-center w-full p-3 relative">
          <span className="font-medium text-base text-center truncate">{theme.name || theme.id}</span>
          {isSelected && (
            <span className="absolute right-3 flex items-center">
              <svg className="h-5 w-5 text-indigo-600 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            </span>
          )}
        </div>
      </li>
    );
  };

  return (
    <div className="relative mt-1 inline-block w-full" ref={dropdownRef}>
      {/* Dropdown Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="relative w-full bg-white border border-gray-300 rounded-md shadow-sm text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm transition-colors hover:border-indigo-300 flex flex-col p-0 overflow-hidden"
      >
        <span className="flex flex-col items-center w-full">
          {selectedTheme ? (
            <>
              <ImageWithFallback src={`${S3_BASE_URL}${selectedTheme.id}.png`} alt={selectedTheme.name || selectedTheme.id} className="w-full aspect-video object-cover shrink-0" />
              <div className="w-full p-3 relative flex items-center justify-center">
                <span className="block truncate font-medium text-base text-gray-900 text-center">{selectedTheme.name || selectedTheme.id}</span>
                <span className="absolute right-3 flex items-center pointer-events-none">
                  <svg className={`h-5 w-5 text-gray-400 transition-transform duration-200 ${isOpen ? 'transform rotate-180' : ''}`} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </span>
              </div>
            </>
          ) : (
            <div className="w-full p-3 relative flex items-center justify-center">
              <span className="text-gray-500 text-center">Выберите тему</span>
              <span className="absolute right-3 flex items-center pointer-events-none">
                <svg className={`h-5 w-5 text-gray-400 transition-transform duration-200 ${isOpen ? 'transform rotate-180' : ''}`} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </span>
            </div>
          )}
        </span>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute z-50 mt-1 w-full bg-white shadow-2xl rounded-md py-2 text-base ring-1 ring-black ring-opacity-10 max-h-[60vh] overflow-y-auto focus:outline-none left-0">
                    <ul role="listbox">
            {themes.map(renderDropdownItem)}
          </ul>
        </div>
      )}
    </div>
  );
}

export default ThemeSelector;
