﻿using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using UniGetUI.Core.Data;
using UniGetUI.Core.IconEngine;
using UniGetUI.Core.Logging;
using UniGetUI.PackageEngine.Classes.Manager.Interfaces;
using UniGetUI.PackageEngine.ManagerClasses.Manager;
using UniGetUI.PackageEngine.PackageClasses;

namespace UniGetUI.PackageEngine.Classes.Manager.BaseProviders
{
    public abstract class BasePackageDetailsProvider<T> : IPackageDetailsProvider where T : PackageManager
    {
        protected T Manager;

        public BasePackageDetailsProvider(T manager)
        {
            Manager = manager;
        }

        public async Task<PackageDetails> GetPackageDetails(Package package)
        {
            return await GetPackageDetails_Unsafe(package);
        }

        public async Task<string[]> GetPackageVersions(Package package)
        {
            if (Manager.Capabilities.SupportsCustomVersions)
                return await GetPackageVersions_Unsafe(package);
            else
            {
                Logger.Warn($"Manager {Manager.Name} does not support version retrieving, this method should have not been called");
                return [];
            }
        }

        public async Task<Uri> GetPackageIconUrl(Package package)
        {
            Uri? Icon = null;
            if (Manager.Capabilities.SupportsCustomPackageIcons)
                Icon = await GetPackageIcon_Unsafe(package);
            else
                Logger.Debug($"Manager {Manager.Name} does not support native icons");

            if (Icon == null)
            {
                var url = IconDatabase.Instance.GetIconUrlForId(package.GetIconId());
                if(url != "") Icon = new Uri(url);
            }

            if (Icon == null)
            {
                Logger.Warn($"Icon for package {package.Id} was not found, returning default icon");
                Icon = new Uri("ms-appx:///Assets/Images/package_color.png");
            }
            else
            { 
                Logger.Info($"Loaded icon with URL={Icon.ToString()} for package Id={package.Id}");
            }
            return Icon;
        }

        public async Task<Uri[]> GetPackageScreenshotsUrl(Package package)
        {
            Uri[] URIs = [];

            if (Manager.Capabilities.SupportsCustomPackageScreenshots)
                URIs = await GetPackageScreenshots_Unsafe(package);
            else
                Logger.Debug($"Manager {Manager.Name} does not support native screenshots");

            if(URIs.Length == 0){
                var UrlArray = IconDatabase.Instance.GetScreenshotsUrlForId(package.Id);
                List<Uri> UriList = new();
                foreach (var url in UrlArray) if (url != "") UriList.Add(new Uri(url));
                URIs = UriList.ToArray();
            }
            Logger.Info($"Found {URIs.Length} screenshots for package Id={package.Id}");
            return URIs;
        }

        protected abstract Task<PackageDetails> GetPackageDetails_Unsafe(Package package);
        protected abstract Task<string[]> GetPackageVersions_Unsafe(Package package);
        protected abstract Task<Uri?> GetPackageIcon_Unsafe(Package package);
        protected abstract Task<Uri[]> GetPackageScreenshots_Unsafe(Package package);
    }
}