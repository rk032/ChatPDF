import React, { useState } from 'react';

const UploadPdf = () => {
  const [statusMessage, setStatusMessage] = useState('');
  const [isUploading, setIsUploading] = useState(false);

  const handleFileUpload = (event) => {
    const file = event.target.files?.[0];

    if (file) {
      if (file.type === 'application/pdf') {
        setIsUploading(true);
        setStatusMessage('Uploading...');

        setTimeout(() => {
          setIsUploading(false);
          setStatusMessage('Success');
        }, 2000);
      } else {
        setStatusMessage('Invalid file. Upload a PDF.');
      }
    }
  };

  return (
    <div className='upload-container'>
      <h2>Upload PDF</h2>
      <input
        type='file'
        accept='application/pdf'
        onChange={handleFileUpload}
        disabled={isUploading}
      />
      <p
        style={{
          color: statusMessage === 'Success' ? 'green' : 'red',
          fontWeight: 'bold',
        }}
      >
        {statusMessage}
      </p>
    </div>
  );
};

export default UploadPdf;
