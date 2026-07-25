import './App.css';

import React from 'react';
import UploadPdf from './UploadPdf';

function App() {
  return (
    <div className='App'>
      <header className='App-header'>
        <h1>PDF Upload</h1>
        <UploadPdf />
      </header>
    </div>
  );
}

export default App;
