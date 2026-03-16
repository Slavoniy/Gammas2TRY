import re

with open('frontend/src/ThemeSelector.jsx', 'r') as f:
    content = f.read()

# Update renderDropdownItem <li>
content = content.replace(
    '''className={`cursor-pointer flex flex-row items-center p-3 hover:bg-indigo-50 transition-colors border-b border-gray-100 last:border-b-0 ${isSelected ? 'bg-indigo-100 text-indigo-900' : 'text-gray-700'}`}''',
    '''className={`cursor-pointer flex flex-col items-center overflow-hidden hover:bg-indigo-50 transition-colors border-b border-gray-100 last:border-b-0 ${isSelected ? 'bg-indigo-100 text-indigo-900' : 'text-gray-700'}`}'''
)

# Update renderDropdownItem content
content = content.replace(
    '''<ImageWithFallback src={imageUrl} alt={theme.name || theme.id} className="w-[160px] h-[90px] object-contain rounded shrink-0 shadow-sm border border-gray-200 mr-4" />
        <div className="flex items-center justify-between w-full overflow-hidden">
          <span className="font-medium text-base truncate">{theme.name || theme.id}</span>
          {isSelected && (
            <svg className="h-5 w-5 text-indigo-600 shrink-0 ml-2" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          )}
        </div>''',
    '''<ImageWithFallback src={imageUrl} alt={theme.name || theme.id} className="w-full h-[225px] object-cover shrink-0" />
        <div className="flex items-center justify-center w-full p-3 relative">
          <span className="font-medium text-base text-center truncate">{theme.name || theme.id}</span>
          {isSelected && (
            <span className="absolute right-3 flex items-center">
              <svg className="h-5 w-5 text-indigo-600 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            </span>
          )}
        </div>'''
)

# Update button class
content = content.replace(
    '''className="relative w-[400px] bg-white border border-gray-300 rounded-md shadow-sm pl-3 pr-10 py-2 text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm transition-colors hover:border-indigo-300"''',
    '''className="relative w-[400px] bg-white border border-gray-300 rounded-md shadow-sm text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm transition-colors hover:border-indigo-300 flex flex-col p-0 overflow-hidden"'''
)

# Update button contents
content = content.replace(
    '''<span className="flex items-center">
          {selectedTheme ? (
            <>
              <ImageWithFallback src={`${S3_BASE_URL}${selectedTheme.id}.png`} alt={selectedTheme.name || selectedTheme.id} className="w-[160px] h-[90px] object-contain rounded shrink-0 shadow-sm border border-gray-200 mr-4" />
              <span className="block truncate font-medium text-base text-gray-900">{selectedTheme.name || selectedTheme.id}</span>
            </>
          ) : (
            <span className="text-gray-500">Выберите тему</span>
          )}
        </span>
        <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
          <svg className={`h-5 w-5 text-gray-400 transition-transform duration-200 ${isOpen ? 'transform rotate-180' : ''}`} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </span>''',
    '''<span className="flex flex-col items-center w-full">
          {selectedTheme ? (
            <>
              <ImageWithFallback src={`${S3_BASE_URL}${selectedTheme.id}.png`} alt={selectedTheme.name || selectedTheme.id} className="w-full h-[225px] object-cover shrink-0" />
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
        </span>'''
)

with open('frontend/src/ThemeSelector.jsx', 'w') as f:
    f.write(content)
