import { ref } from 'vue'
export const nativeWorkspace={workspaceId:ref<string|undefined>('/test-workspace'),ready:ref(true),error:ref<Error>(),refresh:()=>Promise.resolve()}
export function useNativeWorkspace(){return nativeWorkspace}
