const supportedExtensions=[
  '.fits.fz','.fit.fz','.fits','.fit','.fts','.jpg','.jpeg','.png','.tif','.tiff','.bmp','.webp','.heic','.heif','.hif',
  '.cr2','.cr3','.nef','.arw','.dng','.raf','.orf','.rw2','.pef','.srw','.xisf','.ser','.mp4','.mov','.avi','.mkv'
]

export function firstLevelImportFiles(files:File[]){
  return files.filter(file=>{
    if(file.webkitRelativePath.split('/').length!==2)return false
    const name=file.name.toLowerCase()
    return supportedExtensions.some(extension=>name.endsWith(extension))
  })
}
