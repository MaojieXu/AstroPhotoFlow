import {describe,expect,it} from 'vitest'
import {firstLevelImportFiles} from '@ui/modules/data/workspace/folder-selection'

function file(name:string,path:string){
  const value=new File(['image'],name)
  Object.defineProperty(value,'webkitRelativePath',{value:path})
  return value
}

describe('folder import selection',()=>{
  it('keeps supported files directly in the chosen folder and ignores nested or unsupported files',()=>{
    const files=[
      file('one.jpg','night/one.jpg'),file('phone.heic','night/phone.heic'),file('phone.heif','night/phone.heif'),file('three.hif','night/three.hif'),file('two.fits','night/two.fits'),
      file('camera.raf','night/camera.raf'),file('video.ser','night/video.ser'),
      file('nested.png','night/calibration/nested.png'),file('array.npy','night/array.npy')
    ]
    expect(firstLevelImportFiles(files).map(item=>item.name)).toEqual(['one.jpg','phone.heic','phone.heif','three.hif','two.fits','camera.raf','video.ser'])
  })
})
