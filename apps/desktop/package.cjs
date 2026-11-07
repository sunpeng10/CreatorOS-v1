const fs = require('node:fs/promises');
const path = require('node:path');
async function main(){
  const root=path.resolve(__dirname,'../..');
  const target=path.join(root,'data','desktop',`CreatorOS-${require('./package.json').version}`);
  const electron=path.dirname(require('electron'));
  await fs.mkdir(target,{recursive:true});
  await fs.cp(electron,target,{recursive:true});
  const exe=path.join(target,'CreatorOS.exe');
  await fs.copyFile(path.join(target,'electron.exe'),exe);
  await fs.unlink(path.join(target,'electron.exe'));
  const appDir=path.join(target,'resources','app');
  await fs.mkdir(appDir,{recursive:true});
  for(const name of ['main.cjs','services.cjs','splash.html','package.json','assets'])await fs.cp(path.join(__dirname,name),path.join(appDir,name),{recursive:true});
  await fs.writeFile(path.join(appDir,'runtime.json'),JSON.stringify({projectRoot:root}));
  const { rcedit }=await import('rcedit');
  await rcedit(exe,{icon:path.join(__dirname,'assets','creatoros.ico'),'version-string':{ProductName:'CreatorOS',FileDescription:'CreatorOS Desktop',CompanyName:'CreatorOS'},'file-version':'0.1.0','product-version':'0.1.0'});
  await fs.writeFile(path.join(root,'data','desktop','current.json'),JSON.stringify({executable:exe}));
  console.log(exe);
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
